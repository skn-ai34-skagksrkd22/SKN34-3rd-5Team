from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .weather_serializers import WeatherErrorResponseSerializer, WeatherResponseSerializer
from .weather_service import (
    WeatherBusyError,
    WeatherConfigurationError,
    WeatherProviderError,
    WeatherProviderUnavailable,
    WeatherValidationError,
    get_stadium_weather,
)


class StadiumWeatherView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(
        parameters=[
            OpenApiParameter("stadium", str, required=True, description="Canonical stadium code"),
            OpenApiParameter("date", str, required=True, description="KST date (YYYY-MM-DD)"),
            OpenApiParameter("time", str, required=True, description="KST time (HH:MM)"),
        ],
        responses={
            200: WeatherResponseSerializer,
            400: WeatherErrorResponseSerializer,
            429: WeatherErrorResponseSerializer,
            502: WeatherErrorResponseSerializer,
            503: WeatherErrorResponseSerializer,
        },
    )
    def get(self, request):
        try:
            weather = get_stadium_weather(
                request.query_params.get("stadium"),
                request.query_params.get("date"),
                request.query_params.get("time"),
            )
        except WeatherValidationError as error:
            return Response({"weather": None, "error": {"code": error.code}}, status=400)
        except WeatherBusyError as error:
            return Response({"weather": None, "error": {"code": error.code}}, status=429)
        except WeatherConfigurationError as error:
            return Response({"weather": None, "error": {"code": error.code}}, status=503)
        except WeatherProviderUnavailable as error:
            return Response({"weather": None, "error": {"code": error.code}}, status=503)
        except WeatherProviderError as error:
            return Response({"weather": None, "error": {"code": error.code}}, status=502)
        return Response({"weather": weather})
