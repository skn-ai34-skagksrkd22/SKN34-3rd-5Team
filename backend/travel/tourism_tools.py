from django.core.exceptions import PermissionDenied
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Place
from .tourism_models import TourismPlace
from .tourism_serializers import TourismPlaceListSerializer, TourismPlaceWriteSerializer
from .tourism_service import search_tourism


PLACE_FIELDS = {
    "name": "name", "address": "address", "lat": "lat", "lng": "lng", "phone": "phone", "sourceUrl": "url",
}
TOURISM_FIELDS = {"contentId": "content_id", "contentType": "content_type", "category": "category", "imageUrl": "image_url"}


def _data(row):
    place = row.place
    return {
        "id": row.pk, "placeId": place.pk, "contentId": row.content_id, "contentType": row.content_type,
        "name": place.name, "category": row.category, "address": place.address, "lat": place.lat, "lng": place.lng,
        "phone": place.phone, "imageUrl": row.image_url, "sourceUrl": place.url,
        "fetchedAt": row.fetched_at.isoformat() if row.fetched_at else None,
        "lastSyncedAt": row.last_synced_at.isoformat() if row.last_synced_at else None,
    }


def _staff(actor):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or not getattr(actor, "is_staff", False):
        raise PermissionDenied("활성화된 관리자 권한이 필요합니다.")


def _content_id(value):
    if not isinstance(value, str) or not value.isdigit() or len(value) > 255:
        raise ValidationError("content_id는 숫자 문자열이어야 합니다.")
    return value


def _split(values):
    return (
        {field: values[name] for name, field in PLACE_FIELDS.items() if name in values},
        {field: values[name] for name, field in TOURISM_FIELDS.items() if name in values},
    )


def external_tourism_search(arguments):
    return search_tourism(arguments)


def list_tourism_places(arguments=None):
    serializer = TourismPlaceListSerializer(data={} if arguments is None else arguments)
    serializer.is_valid(raise_exception=True)
    query = serializer.validated_data
    rows = TourismPlace.objects.select_related("place")
    if text := query["q"].strip():
        rows = rows.filter(place__name__icontains=text)
    if category := query.get("category"):
        rows = rows.filter(category=category)
    for argument, lookup in (("minLat", "place__lat__gte"), ("maxLat", "place__lat__lte"), ("minLng", "place__lng__gte"), ("maxLng", "place__lng__lte")):
        if argument in query:
            rows = rows.filter(**{lookup: query[argument]})
    start = (query["page"] - 1) * query["pageSize"]
    return {"page": query["page"], "pageSize": query["pageSize"], "items": [_data(row) for row in rows[start:start + query["pageSize"]]]}


def get_tourism_place(content_id):
    return _data(TourismPlace.objects.select_related("place").get(content_id=_content_id(content_id)))


def create_tourism_place(arguments, actor):
    _staff(actor)
    serializer = TourismPlaceWriteSerializer(data=arguments)
    serializer.is_valid(raise_exception=True)
    place_values, tourism_values = _split(serializer.validated_data)
    with transaction.atomic():
        place = Place.objects.create(
            kakao_place_id=None, road_address="", category_group_code="", category_group_name="", category_name="", last_synced_at=None,
            **place_values,
        )
        row = TourismPlace.objects.create(place=place, **tourism_values)
        return _data(row)


def update_tourism_place(content_id, arguments, actor):
    _staff(actor)
    serializer = TourismPlaceWriteSerializer(data=arguments, partial=True)
    serializer.is_valid(raise_exception=True)
    place_values, tourism_values = _split(serializer.validated_data)
    with transaction.atomic():
        row = TourismPlace.objects.select_for_update().get(content_id=_content_id(content_id))
        place = Place.objects.select_for_update().get(pk=row.place_id)
        if place.kakao_place_id is not None and place_values:
            raise ValidationError("카카오 장소의 공통 필드는 관광 도구로 수정할 수 없습니다.")
        for field, value in place_values.items():
            setattr(place, field, value)
        for field, value in tourism_values.items():
            setattr(row, field, value)
        if place_values:
            place.save(update_fields=(*place_values, "updated_at"))
        if tourism_values:
            row.save(update_fields=(*tourism_values, "updated_at"))
        row.place = place
        return _data(row)


def delete_tourism_place(content_id, actor):
    _staff(actor)
    with transaction.atomic():
        row = TourismPlace.objects.select_for_update().get(content_id=_content_id(content_id))
        place = Place.objects.select_for_update().get(pk=row.place_id)
        if place.kakao_place_id is None:
            deleted, _ = place.delete()
        else:
            deleted, _ = row.delete()
    return bool(deleted)
