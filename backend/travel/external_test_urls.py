from django.urls import include, path

from .views import DirectionsView


urlpatterns = [path("travel/directions/", DirectionsView.as_view()), path("", include("travel.urls"))]
