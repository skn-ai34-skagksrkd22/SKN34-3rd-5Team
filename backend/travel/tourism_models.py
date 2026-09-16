from django.db import models
import django.db.models.deletion

from .models import Place


class TourismPlace(models.Model):
    class ContentType(models.TextChoices):
        ATTRACTION = "12", "관광지"
        CULTURE = "14", "문화시설"
        LEISURE = "28", "레포츠"

    class Category(models.TextChoices):
        WALK = "walk", "산책"
        SIGHT = "sight", "관광 명소"
        INDOOR = "indoor", "실내 놀거리"

    place = models.OneToOneField(Place, related_name="tourism", on_delete=django.db.models.deletion.CASCADE)
    content_id = models.CharField(max_length=255, unique=True)
    content_type = models.CharField(max_length=2, choices=ContentType)
    category = models.CharField(max_length=16, choices=Category)
    image_url = models.URLField(max_length=500, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("place__name", "content_id")
