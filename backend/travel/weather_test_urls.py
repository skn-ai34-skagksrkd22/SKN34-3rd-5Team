from django.urls import path

from .weather_views import StadiumWeatherView


urlpatterns = [path("weather/", StadiumWeatherView.as_view())]
