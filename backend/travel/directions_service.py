import json
import math
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .directions_models import DirectionsRoute


def _coordinate(value, limit):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or abs(value) > limit:
        raise ValueError("invalid coordinate")
    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except InvalidOperation:
        raise ValueError("invalid coordinate") from None


def normalize_identity(mode, start, end):
    if mode not in DirectionsRoute.Mode.values or not isinstance(start, dict) or not isinstance(end, dict) or set(start) != {"lat", "lng"} or set(end) != {"lat", "lng"}:
        raise ValueError("invalid directions identity")
    return {
        "mode": mode,
        "start_lat": _coordinate(start["lat"], 90),
        "start_lng": _coordinate(start["lng"], 180),
        "end_lat": _coordinate(end["lat"], 90),
        "end_lng": _coordinate(end["lng"], 180),
    }


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"status", "distance", "seconds", "paths", "instructions"} or payload["status"] != "ok":
        raise ValueError("invalid directions payload")
    try:
        size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
    except (TypeError, ValueError):
        raise ValueError("directions payload must be JSON safe") from None
    if size > 2_000_000:
        raise ValueError("directions payload is too large")
    for field in ("distance", "seconds"):
        value = payload[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 2_147_483_647:
            raise ValueError("invalid directions total")
    paths, instructions = payload["paths"], payload["instructions"]
    if not isinstance(paths, list) or len(paths) > 500 or not isinstance(instructions, list) or len(instructions) > 500 or not all(isinstance(item, str) and len(item) <= 500 for item in instructions):
        raise ValueError("invalid directions details")
    if payload["distance"] > 0 and not paths:
        raise ValueError("missing directions geometry")
    for path in paths:
        if not isinstance(path, list) or not 2 <= len(path) <= 10_000:
            raise ValueError("invalid directions geometry")
        for point in path:
            normalize_identity("walk", point, point)
    return payload


def route_payload(route):
    payload = {"status": "ok", "distance": route.distance, "seconds": route.duration, "paths": route.geometry, "instructions": route.instructions}
    try:
        return validate_payload(payload)
    except ValueError:
        return None


def get_route(mode, start, end):
    identity = normalize_identity(mode, start, end)
    route = DirectionsRoute.objects.filter(**identity).first()
    return route if route is not None and route_payload(route) is not None else None


def sync_route(mode, start, end, payload, *, fetched_at=None):
    identity = normalize_identity(mode, start, end)
    validate_payload(payload)
    fetched_at = timezone.now() if fetched_at is None else fetched_at
    if not isinstance(fetched_at, datetime) or timezone.is_naive(fetched_at):
        raise ValueError("fetched_at must be timezone-aware")
    interval = settings.EXTERNAL_DATA_SYNC_INTERVAL_SECONDS
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        raise ValueError("EXTERNAL_DATA_SYNC_INTERVAL_SECONDS must be positive")
    defaults = {"distance": round(payload["distance"]), "duration": round(payload["seconds"]), "geometry": payload["paths"], "instructions": payload["instructions"], "fetched_at": fetched_at, "last_synced_at": fetched_at}
    with transaction.atomic():
        route, created = DirectionsRoute.objects.select_for_update().get_or_create(**identity, defaults=defaults)
        if created or route_payload(route) is not None and route.last_synced_at is not None and fetched_at - route.last_synced_at <= timedelta(seconds=interval):
            return route
        for field, value in defaults.items():
            setattr(route, field, value)
        route.save(update_fields=tuple(defaults))
        return route


def list_routes(*, mode=None, min_distance=None, max_distance=None, limit=50):
    if mode is not None and mode not in DirectionsRoute.Mode.values or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("invalid directions query")
    queryset = DirectionsRoute.objects.filter(**({"mode": mode} if mode else {}))
    for value, lookup in ((min_distance, "distance__gte"), (max_distance, "distance__lte")):
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("invalid distance filter")
            queryset = queryset.filter(**{lookup: value})
    return list(queryset[:limit])


def replace_route(*, actor, mode, start, end, payload):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or not getattr(actor, "is_staff", False):
        raise PermissionError("trusted active staff actor required")
    identity = normalize_identity(mode, start, end)
    validate_payload(payload)
    with transaction.atomic():
        route, _ = DirectionsRoute.objects.select_for_update().get_or_create(
            **identity,
            defaults={"distance": 0, "duration": 0, "geometry": [], "instructions": []},
        )
        route.distance, route.duration = round(payload["distance"]), round(payload["seconds"])
        route.geometry, route.instructions = payload["paths"], payload["instructions"]
        route.save(update_fields=("distance", "duration", "geometry", "instructions"))
        return route


def delete_route(*, actor, route_id):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False) or not getattr(actor, "is_staff", False):
        raise PermissionError("trusted active staff actor required")
    if not isinstance(route_id, int) or isinstance(route_id, bool) or route_id < 1:
        raise ValueError("invalid route id")
    return DirectionsRoute.objects.filter(pk=route_id).delete()[0]
