from datetime import datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Place
from .tourism_models import TourismPlace
from .tourism_provider import TourismProviderError, fetch_tourism
from .tourism_serializers import ProviderPlaceSerializer, TourismQuerySerializer


PLACE_FIELDS = ("name", "address", "road_address", "category_group_code", "category_group_name", "category_name", "phone", "lat", "lng", "url")
TOURISM_FIELDS = ("content_type", "category", "image_url")


def _values(place):
    return (
        {
            "name": place["name"], "address": place["address"], "road_address": "",
            "category_group_code": "", "category_group_name": "", "category_name": "",
            "phone": place["phone"], "lat": place["lat"], "lng": place["lng"], "url": place.get("sourceUrl", ""),
        },
        {"content_type": place["contentTypeId"], "category": place["kind"], "image_url": place.get("imageUrl", "")},
    )


def sync_tourism_places(places, fetched_at):
    if not isinstance(places, list) or len(places) > 1000:
        raise ValidationError("관광 장소 응답 크기를 확인해 주세요.")
    serializer = ProviderPlaceSerializer(data=places, many=True)
    serializer.is_valid(raise_exception=True)
    if not isinstance(fetched_at, datetime) or timezone.is_naive(fetched_at):
        raise ValueError("fetched_at must be timezone-aware")
    interval = getattr(settings, "EXTERNAL_DATA_SYNC_INTERVAL_SECONDS", None)
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        raise ValueError("EXTERNAL_DATA_SYNC_INTERVAL_SECONDS must be positive")
    unique = {place["tourContentId"]: place for place in serializer.validated_data}
    synced = {}
    with transaction.atomic():
        for content_id, item in sorted(unique.items()):
            # ponytail: PostgreSQL advisory locks avoid orphan Place rows during concurrent first sightings.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [f"tourism:{content_id}"])
            tourism = TourismPlace.objects.select_related("place").filter(content_id=content_id).first()
            place_values, tourism_values = _values(item)
            if tourism is None:
                place = Place.objects.create(kakao_place_id=None, last_synced_at=None, **place_values)
                tourism = TourismPlace.objects.create(
                    place=place, content_id=content_id, fetched_at=fetched_at, last_synced_at=fetched_at, **tourism_values,
                )
            else:
                tourism = TourismPlace.objects.select_for_update().get(pk=tourism.pk)
                place = Place.objects.select_for_update().get(pk=tourism.place_id)
                if tourism.last_synced_at is None or fetched_at - tourism.last_synced_at > timedelta(seconds=interval):
                    if place.kakao_place_id is None:
                        for field, value in place_values.items():
                            setattr(place, field, value)
                        place.save(update_fields=(*PLACE_FIELDS, "updated_at"))
                    for field, value in tourism_values.items():
                        setattr(tourism, field, value)
                    tourism.fetched_at = tourism.last_synced_at = fetched_at
                    tourism.save(update_fields=(*TOURISM_FIELDS, "fetched_at", "last_synced_at", "updated_at"))
            synced[content_id] = tourism.last_synced_at
    return synced


def search_tourism(query, *, fetcher=fetch_tourism, now=None):
    serializer = TourismQuerySerializer(data=query)
    serializer.is_valid(raise_exception=True)
    query = serializer.validated_data
    service_key = getattr(settings, "TOUR_API_KEY", "")
    if not isinstance(service_key, str) or not service_key.strip():
        return {"status": "unconfigured", "places": [], "truncated": False, "stale": False, "fetchedAt": None, "lastSyncedAt": None}
    payload = fetcher(query["stadium"], query["lat"], query["lng"], service_key)
    if not isinstance(payload, dict) or set(payload) != {"status", "places", "truncated"} or payload.get("status") not in {"ok", "partial"} or not isinstance(payload.get("truncated"), bool):
        raise TourismProviderError("invalid_upstream_response")
    fetched_at = now or timezone.now()
    synced = sync_tourism_places(payload["places"], fetched_at)
    last_synced = max((value for value in synced.values() if value), default=None)
    return {**payload, "fetchedAt": fetched_at.isoformat(), "lastSyncedAt": last_synced.isoformat() if last_synced else None, "stale": False}
