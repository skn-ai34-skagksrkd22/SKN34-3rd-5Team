import json
import math
from decimal import Decimal, InvalidOperation

from django.db import migrations, models
from django.db.models import Q


def _coordinate(value, limit):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() and abs(number) <= limit else None


def _valid_details(payload):
    geometry, instructions = payload.get("paths"), payload.get("instructions")
    try:
        if len(json.dumps(payload, allow_nan=False).encode()) > 2_000_000:
            return False
    except (TypeError, ValueError):
        return False
    if not isinstance(geometry, list) or len(geometry) > 500 or not isinstance(instructions, list) or len(instructions) > 500 or not all(isinstance(item, str) and len(item) <= 500 for item in instructions):
        return False
    if payload.get("distance", 0) > 0 and not geometry:
        return False
    for path in geometry:
        if not isinstance(path, list) or not 2 <= len(path) <= 10_000:
            return False
        for point in path:
            if not isinstance(point, dict) or set(point) != {"lat", "lng"} or _coordinate(point["lat"], 90) is None or _coordinate(point["lng"], 180) is None:
                return False
    return True


def backfill_directions(apps, schema_editor):
    Snapshot = apps.get_model("travel", "ExternalProviderSnapshot")
    Route = apps.get_model("travel", "DirectionsRoute")
    for snapshot in Snapshot.objects.filter(kind="directions").iterator():
        request, payload = snapshot.request, snapshot.payload
        if not isinstance(request, dict) or not isinstance(payload, dict) or request.get("mode") not in {"car", "walk", "transit"} or payload.get("status") != "ok":
            continue
        start, end = request.get("start"), request.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            continue
        coordinates = (_coordinate(start.get("lat"), 90), _coordinate(start.get("lng"), 180), _coordinate(end.get("lat"), 90), _coordinate(end.get("lng"), 180))
        distance, duration = payload.get("distance"), payload.get("seconds")
        if any(value is None for value in coordinates) or not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 and value <= 2_147_483_647 for value in (distance, duration)) or not _valid_details(payload):
            continue
        Route.objects.get_or_create(
            mode=request["mode"], start_lat=coordinates[0], start_lng=coordinates[1], end_lat=coordinates[2], end_lng=coordinates[3],
            defaults={"distance": round(distance), "duration": round(duration), "geometry": payload["paths"], "instructions": payload["instructions"], "fetched_at": snapshot.fetched_at, "last_synced_at": snapshot.last_synced_at},
        )


class Migration(migrations.Migration):
    dependencies = [("travel", "0006_externalprovidersnapshot")]

    operations = [
        migrations.CreateModel(
            name="DirectionsRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("car", "Car"), ("walk", "Walk"), ("transit", "Transit")], max_length=8)),
                ("start_lat", models.DecimalField(decimal_places=6, max_digits=8)),
                ("start_lng", models.DecimalField(decimal_places=6, max_digits=9)),
                ("end_lat", models.DecimalField(decimal_places=6, max_digits=8)),
                ("end_lng", models.DecimalField(decimal_places=6, max_digits=9)),
                ("distance", models.PositiveIntegerField()),
                ("duration", models.PositiveIntegerField()),
                ("geometry", models.JSONField(default=list)),
                ("instructions", models.JSONField(default=list)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("mode", "start_lat", "start_lng", "end_lat", "end_lng"),
                "constraints": [
                    models.UniqueConstraint(fields=("mode", "start_lat", "start_lng", "end_lat", "end_lng"), name="travel_directions_route_unique"),
                    models.CheckConstraint(condition=Q(("start_lat__range", (-90, 90))), name="directions_start_lat_bounds"),
                    models.CheckConstraint(condition=Q(("start_lng__range", (-180, 180))), name="directions_start_lng_bounds"),
                    models.CheckConstraint(condition=Q(("end_lat__range", (-90, 90))), name="directions_end_lat_bounds"),
                    models.CheckConstraint(condition=Q(("end_lng__range", (-180, 180))), name="directions_end_lng_bounds"),
                ],
            },
        ),
        migrations.RunPython(backfill_directions, migrations.RunPython.noop),
    ]
