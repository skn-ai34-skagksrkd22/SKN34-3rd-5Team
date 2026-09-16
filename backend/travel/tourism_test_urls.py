from django.urls import path

from .tourism_views import TourismSearchView
from .place_views import PlaceDetailView, PlaceListCreateView, PlaceSearchView


urlpatterns = [
    path("places/search/", PlaceSearchView.as_view()),
    path("places/", PlaceListCreateView.as_view()),
    path("places/<int:pk>/", PlaceDetailView.as_view()),
    path("tourism/", TourismSearchView.as_view()),
]
