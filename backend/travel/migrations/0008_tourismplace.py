import math
from urllib.parse import urlsplit

from django.db import migrations, models
from django.db.models import Q


def backfill_tourism_places(apps, schema_editor):
    Snapshot = apps.get_model("travel", "ExternalProviderSnapshot")
    TourismPlace = apps.get_model("travel", "TourismPlace")
    rows = []
    categories = {"walk": "산책", "sight": "관광 명소", "indoor": "실내 놀거리"}
    for snapshot in Snapshot.objects.filter(kind="tourism").iterator():
        payload = snapshot.payload
        places = payload.get("places") if isinstance(payload, dict) else None
        if not isinstance(places, list):
            continue
        for place in places:
            if not isinstance(place, dict):
                continue
            content_id, content_type, name, category = place.get("tourContentId"), place.get("contentTypeId"), place.get("name"), place.get("kind")
            lat, lng = place.get("lat"), place.get("lng")
            if not isinstance(content_id, str) or not content_id.isdigit() or content_type not in {"12", "14", "28"} or not isinstance(name, str) or not name.strip() or category not in categories:
                continue
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (lat, lng)) or abs(lat) > 90 or abs(lng) > 180:
                continue
            address, phone = place.get("address", ""), place.get("phone", "")
            if not isinstance(address, str) or len(address) > 500 or not isinstance(phone, str) or len(phone) > 120:
                continue
            urls = []
            for field in ("imageUrl", "sourceUrl"):
                value = place.get(field, "")
                parsed = urlsplit(value) if isinstance(value, str) else None
                urls.append(value if parsed and parsed.scheme == "https" and parsed.netloc and len(value) <= 500 else "")
            rows.append(TourismPlace(
                content_id=content_id, content_type=content_type, name=name.strip(), category=category,
                address=address, latitude=lat, longitude=lng, phone=phone, image_url=urls[0], source_url=urls[1],
                fetched_at=snapshot.fetched_at, last_synced_at=snapshot.last_synced_at,
            ))
    TourismPlace.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("travel", "0007_directionsroute")]

    operations = [
        migrations.CreateModel(
            name="TourismPlace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_id", models.CharField(max_length=255, unique=True)),
                ("content_type", models.CharField(choices=[("12", "관광지"), ("14", "문화시설"), ("28", "레포츠")], max_length=2)),
                ("name", models.CharField(max_length=255)),
                ("category", models.CharField(choices=[("walk", "산책"), ("sight", "관광 명소"), ("indoor", "실내 놀거리")], max_length=16)),
                ("address", models.CharField(blank=True, max_length=500)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("phone", models.CharField(blank=True, max_length=120)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("source_url", models.URLField(blank=True, max_length=500)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("name", "content_id"),
                "constraints": [
                    models.CheckConstraint(condition=Q(latitude__range=(-90, 90)), name="tourism_place_lat_bounds"),
                    models.CheckConstraint(condition=Q(longitude__range=(-180, 180)), name="tourism_place_lng_bounds"),
                ],
            },
        ),
        migrations.RunPython(backfill_tourism_places, migrations.RunPython.noop),
    ]
