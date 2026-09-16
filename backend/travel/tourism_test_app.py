from importlib import import_module

from .apps import TravelConfig


class TourismTravelConfig(TravelConfig):
    def import_models(self):
        super().import_models()
        import_module("travel.tourism_models")
