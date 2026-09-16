import json
import math
import re
import socket
import threading
from http.client import HTTPException
from datetime import date as date_type
from datetime import datetime, time as time_type, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


KST = timezone(timedelta(hours=9))
KMA_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
ISSUE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)
MAX_RESPONSE_BYTES = 1024 * 1024
_slots = threading.BoundedSemaphore(4)

STADIUM_COORDINATES = {
    "JAMSIL": (37.5161987797456, 127.075940589715),
    "GOCHEOK": (37.4982125677913, 126.867088741096),
    "MUNHAK": (37.4350819826381, 126.690759830613),
    "SUWON": (37.2978428909635, 127.011348102567),
    "DAEJEON": (36.3173370007388, 127.428013823451),
    "DAEGU": (35.8411289243023, 128.681236372268),
    "GWANGJU": (35.1694249627659, 126.888805470329),
    "SAJIK": (35.194366802896, 129.059900885997),
    "CHANGWON": (35.2219848625101, 128.579580117268),
}


class WeatherError(Exception):
    code = "weather_unavailable"


class WeatherValidationError(WeatherError):
    code = "invalid_request"


class WeatherConfigurationError(WeatherError):
    code = "weather_not_configured"


class WeatherBusyError(WeatherError):
    code = "weather_busy"


class WeatherProviderError(WeatherError):
    code = "provider_response_invalid"


class WeatherProviderUnavailable(WeatherError):
    code = "provider_unavailable"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def lambert_grid(latitude, longitude):
    rad = math.pi / 180
    re_value = 6371.00877 / 5
    sn = math.log(math.cos(30 * rad) / math.cos(60 * rad)) / math.log(
        math.tan(math.pi / 4 + 60 * rad / 2) / math.tan(math.pi / 4 + 30 * rad / 2)
    )
    sf = math.tan(math.pi / 4 + 30 * rad / 2) ** sn * math.cos(30 * rad) / sn
    ro = re_value * sf / math.tan(math.pi / 4 + 38 * rad / 2) ** sn
    ra = re_value * sf / math.tan(math.pi / 4 + latitude * rad / 2) ** sn
    theta = (longitude - 126) * rad * sn
    return math.floor(ra * math.sin(theta) + 43.5), math.floor(ro - ra * math.cos(theta) + 136.5)


def _target_datetime(date_value, time_value, now):
    if not isinstance(date_value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        raise WeatherValidationError("date must use YYYY-MM-DD")
    if not isinstance(time_value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_value):
        raise WeatherValidationError("time must use HH:MM")
    try:
        target = datetime.combine(date_type.fromisoformat(date_value), time_type.fromisoformat(time_value), KST)
    except ValueError:
        raise WeatherValidationError("date or time is not a real calendar value") from None
    if target < now - timedelta(days=1) or target > now + timedelta(days=5):
        raise WeatherValidationError("target must be within the previous 24 hours and next 120 hours")
    return target


def _issue_datetime(now, target):
    cutoff = min(now, target) - timedelta(hours=1)
    for hour in reversed(ISSUE_HOURS):
        candidate = cutoff.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate <= cutoff:
            return candidate
    return (cutoff - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)


def _forecast_datetime(target):
    # JavaScript Math.round semantics: a half-hour rounds toward the next hour.
    hours = math.floor(target.timestamp() / 3600 + 0.5)
    return datetime.fromtimestamp(hours * 3600, KST)


def _service_key():
    raw = str(getattr(settings, "KMA_SERVICE_KEY", "") or "").strip()
    raw = raw or str(getattr(settings, "KMA_API_KEY", "") or "").strip()
    if not raw:
        raise WeatherConfigurationError("KMA service key is not configured")
    if len(raw) > 512 or re.search(r"%(?![0-9A-Fa-f]{2})", raw):
        raise WeatherConfigurationError("KMA service key is invalid")
    try:
        key = unquote(raw, errors="strict")
    except UnicodeDecodeError:
        raise WeatherConfigurationError("KMA service key is invalid") from None
    if not key or any(character.isspace() or ord(character) < 32 for character in key):
        raise WeatherConfigurationError("KMA service key is invalid")
    return key


def _request_items(issue, nx, ny):
    query = urlencode({
        "serviceKey": _service_key(),
        "pageNo": "1",
        "numOfRows": "2000",
        "dataType": "JSON",
        "base_date": issue.strftime("%Y%m%d"),
        "base_time": issue.strftime("%H00"),
        "nx": str(nx),
        "ny": str(ny),
    })
    request = Request(f"{KMA_URL}?{query}", headers={"Accept": "application/json"})
    try:
        response = build_opener(_NoRedirect).open(request, timeout=12)
        with response:
            content_type = response.headers.get_content_type()
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        if 300 <= error.code < 400:
            raise WeatherProviderError("KMA redirected unexpectedly") from None
        raise WeatherProviderUnavailable("KMA request failed") from None
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException):
        raise WeatherProviderUnavailable("KMA request failed") from None
    except (AttributeError, ValueError):
        raise WeatherProviderError("KMA response metadata is invalid") from None
    if content_type not in {"application/json", "text/json"} or len(payload) > MAX_RESPONSE_BYTES:
        raise WeatherProviderError("KMA response metadata is invalid")
    try:
        body = json.loads(payload)
        header = body["response"]["header"]
        result_code = str(header["resultCode"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise WeatherProviderError("KMA response is invalid") from None
    if result_code == "03":
        return []
    if result_code != "00":
        raise WeatherProviderError("KMA rejected the request")
    try:
        items = body["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        raise WeatherProviderError("KMA response items are invalid") from None
    if not isinstance(items, list) or len(items) > 2000:
        raise WeatherProviderError("KMA response items are invalid")
    expected = {"baseDate": issue.strftime("%Y%m%d"), "baseTime": issue.strftime("%H00"), "nx": str(nx), "ny": str(ny)}
    for item in items:
        if not isinstance(item, dict):
            raise WeatherProviderError("KMA response item is invalid")
        if any(key in item and str(item[key]) != value for key, value in expected.items()):
            raise WeatherProviderError("KMA response scope is invalid")
    return items


def _weather_from_items(items, forecast, issue, fetched_at):
    forecast_date, forecast_time = forecast.strftime("%Y%m%d"), forecast.strftime("%H00")
    matched = []
    for item in items:
        if not isinstance(item, dict):
            raise WeatherProviderError("KMA response item is invalid")
        if item.get("fcstDate") == forecast_date and item.get("fcstTime") == forecast_time:
            matched.append(item)
    if not matched:
        return None
    values = {}
    for item in matched:
        category = item.get("category")
        if isinstance(category, str) and category in {"TMP", "SKY", "PTY"}:
            value = item.get("fcstValue")
            if not isinstance(value, (str, int, float)):
                raise WeatherProviderError("KMA forecast value is invalid")
            text = str(value).strip()
            if category in values and values[category] != text:
                raise WeatherProviderError("KMA forecast values conflict")
            values[category] = text
    if set(values) != {"TMP", "SKY", "PTY"}:
        raise WeatherProviderError("KMA forecast is incomplete")
    try:
        temperature = float(values["TMP"])
        sky_code = int(values["SKY"])
        precipitation_code = int(values["PTY"])
    except ValueError:
        raise WeatherProviderError("KMA forecast value is invalid") from None
    sky = {1: "맑음", 3: "구름많음", 4: "흐림"}.get(sky_code)
    precipitation = {0: None, 1: "비", 2: "비/눈", 3: "눈", 4: "소나기"}.get(precipitation_code)
    if not math.isfinite(temperature) or sky is None or precipitation_code not in {0, 1, 2, 3, 4}:
        raise WeatherProviderError("KMA forecast value is invalid")
    return {
        "label": precipitation or sky,
        "temperature": temperature,
        "forecastAt": forecast.isoformat(timespec="minutes"),
        "issuedAt": issue.isoformat(timespec="minutes"),
        "fetchedAt": fetched_at.isoformat(timespec="seconds"),
        "source": "기상청 단기예보",
    }


def get_stadium_weather(stadium_code, date, time, *, now=None):
    if not isinstance(stadium_code, str) or stadium_code not in STADIUM_COORDINATES:
        raise WeatherValidationError("stadium must be a supported stadium code")
    now = now or datetime.now(KST)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be a timezone-aware datetime")
    now = now.astimezone(KST)
    target = _target_datetime(date, time, now)
    issue = _issue_datetime(now, target)
    forecast = _forecast_datetime(target)
    nx, ny = lambert_grid(*STADIUM_COORDINATES[stadium_code])
    if not _slots.acquire(blocking=False):
        raise WeatherBusyError("too many weather requests")
    try:
        return _weather_from_items(_request_items(issue, nx, ny), forecast, issue, datetime.now(KST))
    finally:
        _slots.release()
