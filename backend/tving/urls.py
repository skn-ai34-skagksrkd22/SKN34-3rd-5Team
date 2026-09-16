from django.urls import path

from .views import AthleteView, DailyView, DetailsStatusView, EntityListView, MonthView, PlayerEntityDetailView, PlayerEntityListView, SnapshotDetailView, SnapshotListView, TeamView


urlpatterns = [
    path("daily/", DailyView.as_view(), name="tving-daily"),
    path("schedule/", MonthView.as_view(), name="tving-month"),
    path("details/teams/<str:value>/", TeamView.as_view(), name="tving-team"),
    path("details/athletes/<str:value>/", AthleteView.as_view(), name="tving-athlete"),
    path("details/status/", DetailsStatusView.as_view(), name="tving-details-status"),
    path("entities/", EntityListView.as_view(), name="tving-entity-list"),
    path("entities/players/", PlayerEntityListView.as_view(), name="tving-player-create"),
    path("entities/players/<str:code>/", PlayerEntityDetailView.as_view(), name="tving-player-detail"),
    path("snapshots/", SnapshotListView.as_view(), name="tving-snapshot-list"),
    path("snapshots/<int:pk>/", SnapshotDetailView.as_view(), name="tving-snapshot-detail"),
]
