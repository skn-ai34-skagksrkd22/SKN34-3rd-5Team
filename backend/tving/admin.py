from django.contrib import admin

from baseball import models
from baseball.models import ProviderSnapshot


@admin.register(ProviderSnapshot)
class ProviderSnapshotAdmin(admin.ModelAdmin):
    list_display = ("resource_kind", "resource_key", "source_fetched_at", "last_synced_at")
    list_filter = ("resource_kind",)
    search_fields = ("resource_key",)
    readonly_fields = ("created_at", "updated_at")


admin.site.register([
    models.Player, models.PlayerCareerRecord,
    models.PlayerSeasonRecord, models.ScheduleDay, models.TeamProfile,
    models.TeamRoster, models.TeamSeasonRecord,
    models.TeamTopPlayer,
])
