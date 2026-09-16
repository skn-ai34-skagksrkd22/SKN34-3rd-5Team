from django.db import models
from django.db.models import Q


class DirectionsRoute(models.Model):
    class Mode(models.TextChoices):
        CAR = "car"
        WALK = "walk"
        TRANSIT = "transit"

    mode = models.CharField(max_length=8, choices=Mode)
    start_lat = models.DecimalField(max_digits=8, decimal_places=6)
    start_lng = models.DecimalField(max_digits=9, decimal_places=6)
    end_lat = models.DecimalField(max_digits=8, decimal_places=6)
    end_lng = models.DecimalField(max_digits=9, decimal_places=6)
    distance = models.PositiveIntegerField()
    duration = models.PositiveIntegerField()
    geometry = models.JSONField(default=list)
    instructions = models.JSONField(default=list)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("mode", "start_lat", "start_lng", "end_lat", "end_lng")
        constraints = (
            models.UniqueConstraint(fields=("mode", "start_lat", "start_lng", "end_lat", "end_lng"), name="travel_directions_route_unique"),
            models.CheckConstraint(condition=Q(start_lat__range=(-90, 90)), name="directions_start_lat_bounds"),
            models.CheckConstraint(condition=Q(start_lng__range=(-180, 180)), name="directions_start_lng_bounds"),
            models.CheckConstraint(condition=Q(end_lat__range=(-90, 90)), name="directions_end_lat_bounds"),
            models.CheckConstraint(condition=Q(end_lng__range=(-180, 180)), name="directions_end_lng_bounds"),
        )
