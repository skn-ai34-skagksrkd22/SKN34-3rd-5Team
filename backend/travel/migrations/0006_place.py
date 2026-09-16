from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("travel", "0005_course_engagement")]

    operations = [
        migrations.CreateModel(
            name="Place",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kakao_place_id", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("address", models.CharField(blank=True, max_length=500)),
                ("road_address", models.CharField(blank=True, max_length=500)),
                ("category_group_code", models.CharField(blank=True, max_length=20)),
                ("category_group_name", models.CharField(blank=True, max_length=100)),
                ("category_name", models.CharField(blank=True, max_length=255)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("lat", models.FloatField()),
                ("lng", models.FloatField()),
                ("url", models.URLField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("id",),
                "constraints": [
                    models.CheckConstraint(condition=Q(lat__range=(-90, 90)), name="place_lat_bounds"),
                    models.CheckConstraint(condition=Q(lng__range=(-180, 180)), name="place_lng_bounds"),
                ],
            },
        ),
    ]
