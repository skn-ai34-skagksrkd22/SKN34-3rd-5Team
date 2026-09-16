import hashlib
import json
import math
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ExternalProviderSnapshot


MODES = {"car", "walk", "transit"}


def _point(value):
    if not isinstance(value, dict) or set(value) != {"lat", "lng"}:
        raise ValueError("invalid point")
    lat, lng = value["lat"], value["lng"]
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in (lat, lng)) or abs(lat) > 90 or abs(lng) > 180:
        raise ValueError("invalid point")


def _directions(kind, key, request, payload):
    if set(request) != {"mode", "start", "end"} or request["mode"] not in MODES:
        raise ValueError("invalid directions request")
    _point(request["start"])
    _point(request["end"])
    expected = f"{request['mode']}:{request['start']['lng']:.6f},{request['start']['lat']:.6f}:{request['end']['lng']:.6f},{request['end']['lat']:.6f}"
    if key != expected or set(payload) != {"status", "distance", "seconds", "paths", "instructions"} or payload["status"] != "ok":
        raise ValueError("invalid directions snapshot")
    for name in ("distance", "seconds"):
        value = payload[name]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid directions totals")
    if not isinstance(payload["paths"], list) or len(payload["paths"]) > 500 or not isinstance(payload["instructions"], list) or len(payload["instructions"]) > 500:
        raise ValueError("invalid directions details")
    for path in payload["paths"]:
        if not isinstance(path, list) or not 2 <= len(path) <= 10_000:
            raise ValueError("invalid directions geometry")
        for point in path:
            _point(point)
    if not all(isinstance(item, str) and len(item) <= 500 for item in payload["instructions"]):
        raise ValueError("invalid directions instructions")


def _tourism(kind, key, request, payload):
    if set(request) != {"stadium", "lat", "lng", "radius", "contentTypes", "pageSize", "maxPages"} or not isinstance(request["stadium"], str) or not re.fullmatch(r"[A-Z0-9_]{1,32}", request["stadium"]):
        raise ValueError("invalid tourism request")
    _point({"lat": request["lat"], "lng": request["lng"]})
    integers = (request["radius"], request["pageSize"], request["maxPages"])
    if request["lat"] != round(request["lat"], 6) or request["lng"] != round(request["lng"], 6) or any(not isinstance(value, int) or isinstance(value, bool) for value in integers) or integers != (2500, 100, 3) or request["contentTypes"] != ["12", "14", "28"]:
        raise ValueError("invalid tourism request")
    expected = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if key != expected or set(payload) != {"status", "places", "truncated"} or payload["status"] != "ok" or payload["truncated"] is not False:
        raise ValueError("invalid tourism snapshot")
    places = payload["places"]
    if not isinstance(places, list) or len(places) > 1_000:
        raise ValueError("invalid tourism places")
    for place in places:
        required = {"placeId", "tourContentId", "name", "lat", "lng", "category", "kind", "cuisine", "address", "phone", "detail", "distance"}
        if not isinstance(place, dict) or not required <= set(place) <= required | {"subcategory"}:
            raise ValueError("invalid tourism place")
        content_id = place["tourContentId"]
        category = {"walk": "산책", "sight": "관광 명소", "indoor": "실내 놀거리"}.get(place["kind"])
        strings = (("name", 255, False), ("address", 500, True), ("phone", 120, True), ("detail", 500, False))
        if not isinstance(content_id, str) or not content_id.isdigit() or len(content_id) > 255 or place["placeId"] != f"tour:{content_id}" or category != place["category"] or place["cuisine"] != "기타":
            raise ValueError("invalid tourism place")
        if any(not isinstance(place[name], str) or len(place[name]) > limit or not allow_blank and not place[name].strip() for name, limit, allow_blank in strings):
            raise ValueError("invalid tourism place")
        if "subcategory" in place and (not isinstance(place["subcategory"], str) or not place["subcategory"].strip() or len(place["subcategory"]) > 120):
            raise ValueError("invalid tourism place")
        _point({"lat": place.get("lat"), "lng": place.get("lng")})
        distance = place["distance"]
        if not isinstance(distance, (int, float)) or isinstance(distance, bool) or not math.isfinite(distance) or not 0 <= distance <= 2500:
            raise ValueError("invalid tourism place")


VALIDATORS = {"directions": _directions, "tourism": _tourism}


def _validate(kind, key, request, payload):
    if kind not in ExternalProviderSnapshot.Kind.values:
        raise ValueError("unsupported snapshot kind")
    if not isinstance(key, str) or not key.strip() or len(key.strip()) > 255:
        raise ValueError("snapshot key must be 1..255 characters")
    if not isinstance(request, dict) or len(request) > 32 or not isinstance(payload, dict):
        raise ValueError("snapshot request and payload must be bounded objects")
    try:
        request_size = len(json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
        payload_size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
    except (TypeError, ValueError):
        raise ValueError("snapshot data must be JSON serializable") from None
    if request_size > 12_000 or payload_size > 2_000_000:
        raise ValueError("snapshot data is too large")
    VALIDATORS[kind](kind, key.strip(), request, payload)
    return key.strip()


def sync_snapshot(kind, key, request, payload, *, fetched_at=None):
    """Conditionally persist a fully provider-validated payload and return the stored row."""
    key = _validate(kind, key, request, payload)
    fetched_at = timezone.now() if fetched_at is None else fetched_at
    if not isinstance(fetched_at, datetime) or timezone.is_naive(fetched_at):
        raise ValueError("fetched_at must be timezone-aware")
    interval = settings.EXTERNAL_DATA_SYNC_INTERVAL_SECONDS
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        raise ValueError("EXTERNAL_DATA_SYNC_INTERVAL_SECONDS must be positive")
    with transaction.atomic():
        snapshot, created = ExternalProviderSnapshot.objects.select_for_update().get_or_create(
            kind=kind,
            key=key,
            defaults={"request": request, "payload": payload, "last_synced_at": fetched_at, "fetched_at": fetched_at},
        )
        valid_existing = True
        if not created:
            try:
                _validate(snapshot.kind, snapshot.key, snapshot.request, snapshot.payload)
            except ValueError:
                valid_existing = False
        if created or valid_existing and snapshot.last_synced_at is not None and fetched_at - snapshot.last_synced_at <= timedelta(seconds=interval):
            return snapshot
        snapshot.request = request
        snapshot.payload = payload
        snapshot.last_synced_at = fetched_at
        snapshot.fetched_at = fetched_at
        snapshot.save(update_fields=("request", "payload", "last_synced_at", "fetched_at"))
        return snapshot


def get_snapshot(kind, key):
    if kind not in ExternalProviderSnapshot.Kind.values or not isinstance(key, str) or not key.strip() or len(key.strip()) > 255:
        raise ValueError("invalid snapshot identity")
    snapshot = ExternalProviderSnapshot.objects.filter(kind=kind, key=key.strip()).first()
    if snapshot:
        try:
            _validate(snapshot.kind, snapshot.key, snapshot.request, snapshot.payload)
        except ValueError:
            return None
    return snapshot


def list_snapshots(*, kind=None, text="", limit=50):
    if kind is not None and kind not in ExternalProviderSnapshot.Kind.values:
        raise ValueError("unsupported snapshot kind")
    if not isinstance(text, str) or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("invalid snapshot query")
    queryset = ExternalProviderSnapshot.objects.filter(**({"kind": kind} if kind else {}))
    if text:
        queryset = queryset.filter(key__icontains=text[:120])
    return list(queryset[:limit])


def replace_snapshot(*, actor, kind, key, request, payload):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or not getattr(actor, "is_staff", False):
        raise PermissionError("trusted staff actor required")
    key = _validate(kind, key, request, payload)
    with transaction.atomic():
        snapshot, _ = ExternalProviderSnapshot.objects.select_for_update().get_or_create(kind=kind, key=key)
        snapshot.request, snapshot.payload = request, payload
        snapshot.save(update_fields=("request", "payload"))
        return snapshot


def delete_snapshot(*, actor, snapshot_id):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or not getattr(actor, "is_staff", False):
        raise PermissionError("trusted staff actor required")
    if not isinstance(snapshot_id, int) or isinstance(snapshot_id, bool) or snapshot_id < 1:
        raise ValueError("invalid snapshot id")
    return ExternalProviderSnapshot.objects.filter(pk=snapshot_id).delete()[0]
