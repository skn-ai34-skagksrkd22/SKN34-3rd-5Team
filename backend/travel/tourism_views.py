from django.conf import settings
from threading import BoundedSemaphore
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema

from .tourism_provider import TourismProviderError
from .tourism_serializers import TourismQuerySerializer, TourismResponseSerializer
from .tourism_service import search_tourism


# ponytail: process-local cap; use a shared limiter only if multi-worker pressure is measured.
_tourism_slots = BoundedSemaphore(3)


class TourismThrottle(SimpleRateThrottle):
    scope = "tourism"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class TourismSearchView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (TourismThrottle,)

    @extend_schema(parameters=[OpenApiParameter("stadium", str, required=True), OpenApiParameter("lat", float, required=True), OpenApiParameter("lng", float, required=True)], responses={200: TourismResponseSerializer, 400: TourismResponseSerializer, 429: TourismResponseSerializer, 502: TourismResponseSerializer, 503: TourismResponseSerializer}, auth=[])
    def get(self, request):
        serializer = TourismQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        service_key = getattr(settings, "TOUR_API_KEY", "")
        if not isinstance(service_key, str) or not service_key.strip():
            return Response({"status": "unconfigured", "places": [], "truncated": False, "stale": False, "fetchedAt": None, "lastSyncedAt": None})
        if not _tourism_slots.acquire(blocking=False):
            return Response({"status": "error", "places": [], "truncated": False}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            return Response(search_tourism(serializer.validated_data))
        except TourismProviderError as error:
            return Response({"status": "error", "places": [], "truncated": False}, status=error.status)
        except Exception:
            return Response({"status": "error", "places": [], "truncated": False}, status=status.HTTP_502_BAD_GATEWAY)
        finally:
            _tourism_slots.release()
