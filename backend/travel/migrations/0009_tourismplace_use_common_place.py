import django.db.models.deletion
from django.db import migrations, models


def move_common_fields_to_place(apps, schema_editor):
    Place = apps.get_model("travel", "Place")
    TourismPlace = apps.get_model("travel", "TourismPlace")
    db = schema_editor.connection.alias
    for tourism in TourismPlace.objects.using(db).select_for_update().filter(place__isnull=True).order_by("content_id"):
        place = Place.objects.using(db).create(
            kakao_place_id=None,
            name=tourism.name,
            address=tourism.address,
            road_address="",
            category_group_code="",
            category_group_name="",
            category_name="",
            phone=tourism.phone,
            lat=tourism.latitude,
            lng=tourism.longitude,
            url=tourism.source_url,
            last_synced_at=None,
        )
        tourism.place_id = place.pk
        tourism.save(update_fields=("place",))


def restore_common_fields(apps, schema_editor):
    TourismPlace = apps.get_model("travel", "TourismPlace")
    db = schema_editor.connection.alias
    for tourism in TourismPlace.objects.using(db).select_related("place").order_by("content_id"):
        place = tourism.place
        TourismPlace.objects.using(db).filter(pk=tourism.pk).update(
            name=place.name, address=place.address, latitude=place.lat, longitude=place.lng,
            phone=place.phone, source_url=place.url,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("travel", "0006_place"),
        ("travel", "0008_tourismplace"),
    ]

    operations = [
        migrations.AlterField(
            model_name="place",
            name="phone",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="tourismplace",
            name="place",
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="tourism", to="travel.place"),
        ),
        migrations.AlterField(model_name="tourismplace", name="name", field=models.CharField(max_length=255, null=True)),
        migrations.AlterField(model_name="tourismplace", name="address", field=models.CharField(blank=True, max_length=500, null=True)),
        migrations.AlterField(model_name="tourismplace", name="latitude", field=models.FloatField(null=True)),
        migrations.AlterField(model_name="tourismplace", name="longitude", field=models.FloatField(null=True)),
        migrations.AlterField(model_name="tourismplace", name="phone", field=models.CharField(blank=True, max_length=120, null=True)),
        migrations.AlterField(model_name="tourismplace", name="source_url", field=models.URLField(blank=True, max_length=500, null=True)),
        migrations.RunPython(move_common_fields_to_place, restore_common_fields),
        migrations.AlterField(
            model_name="tourismplace",
            name="place",
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="tourism", to="travel.place"),
        ),
        migrations.RemoveConstraint(model_name="tourismplace", name="tourism_place_lat_bounds"),
        migrations.RemoveConstraint(model_name="tourismplace", name="tourism_place_lng_bounds"),
        migrations.RemoveField(model_name="tourismplace", name="name"),
        migrations.RemoveField(model_name="tourismplace", name="address"),
        migrations.RemoveField(model_name="tourismplace", name="latitude"),
        migrations.RemoveField(model_name="tourismplace", name="longitude"),
        migrations.RemoveField(model_name="tourismplace", name="phone"),
        migrations.RemoveField(model_name="tourismplace", name="source_url"),
        migrations.AlterModelOptions(name="tourismplace", options={"ordering": ("place__name", "content_id")}),
    ]
