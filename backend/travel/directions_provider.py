import json
import math
import threading
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

from .directions_service import get_route, route_payload, sync_route


ENDPOINTS = {
    "car": ("apis-navi.kakaomobility.com", "/v1/directions"),
    "walk": ("dapi.kakao.com", "/v2/routing/walk"),
    "transit": ("dapi.kakao.com", "/v2/routing/publictraffic"),
}
_slots = threading.BoundedSemaphore(3)


class DirectionsError(Exception):
    def __init__(self, status=502):
        self.status = status
        super().__init__("directions provider unavailable")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(mode, params, key, fetcher=None):
    host, path = ENDPOINTS[mode]
    if not _slots.acquire(blocking=False):
        raise DirectionsError(429)
    try:
        if fetcher:
            return fetcher(host, path, params, key)
        request = Request(f"https://{host}{path}?{urlencode(params)}", headers={"Accept": "application/json", "Authorization": f"KakaoAK {key}"})
        with build_opener(_NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or "json" not in response.headers.get_content_type():
                raise DirectionsError(429 if response.status == 429 else 502)
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise DirectionsError()
            return json.loads(raw)
    except HTTPError as exc:
        raise DirectionsError(429 if exc.code == 429 else 502) from None
    except DirectionsError:
        raise
    except (HTTPException, URLError, TimeoutError, ValueError, OSError):
        raise DirectionsError() from None
    finally:
        _slots.release()


def _amount(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def _geometry(steps):
    if not isinstance(steps, list) or not steps:
        raise DirectionsError()
    paths, instructions = [], []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("path"), dict) or not isinstance(step["path"].get("points"), list):
            raise DirectionsError()
        path = []
        for pair in step["path"]["points"]:
            if not isinstance(pair, list) or len(pair) != 2:
                raise DirectionsError()
            lng, lat = pair
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lng)) or abs(lat) > 90 or abs(lng) > 180:
                raise DirectionsError()
            path.append({"lat": lat, "lng": lng})
        if len(path) < 2:
            raise DirectionsError()
        if len(path) > 1:
            paths.append(path)
        properties = step.get("properties", {})
        if not isinstance(properties, dict):
            raise DirectionsError()
        guidance = properties.get("guidance")
        if isinstance(guidance, str) and guidance:
            instructions.append(guidance)
    return paths, instructions


def parse_directions(mode, value):
    if mode not in ENDPOINTS or not isinstance(value, dict):
        raise DirectionsError()
    data = value
    status = data.get("status")
    if isinstance(status, str) and status in {"SAME_POINT", "EQUAL_POINTS"}:
        return {"status": "ok", "distance": 0, "seconds": 0, "paths": [], "instructions": ["출발지와 도착지가 같은 위치예요."]}
    if mode == "car":
        routes = data.get("routes")
        if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
            raise DirectionsError()
        route = routes[0]
        if route.get("result_code") != 0:
            raise DirectionsError()
        summary = route.get("summary")
        if not isinstance(summary, dict) or not isinstance(route.get("sections"), list):
            raise DirectionsError()
        distance, seconds = _amount(summary.get("distance")), _amount(summary.get("duration"))
        steps = []
        for section in route["sections"]:
            if not isinstance(section, dict) or not isinstance(section.get("roads"), list):
                raise DirectionsError()
            for road in section["roads"]:
                if not isinstance(road, dict):
                    raise DirectionsError()
                vertices = road.get("vertexes")
                if not isinstance(vertices, list) or len(vertices) < 4 or len(vertices) % 2:
                    raise DirectionsError()
                pairs = [vertices[i:i + 2] for i in range(0, len(vertices), 2)]
                name = road.get("name")
                steps.append({"path": {"points": pairs}, "properties": {"guidance": f"{name} 이동" if isinstance(name, str) and name else "도로 이동"}})
    else:
        if not isinstance(status, str) or status != "OK":
            raise DirectionsError()
        if mode == "walk":
            route = data.get("route")
            if not isinstance(route, dict) or not isinstance(route.get("legs"), list):
                raise DirectionsError()
            steps = []
            for leg in route["legs"]:
                if not isinstance(leg, dict) or not isinstance(leg.get("steps"), list):
                    raise DirectionsError()
                steps.extend(leg["steps"])
        else:
            routes = data.get("routes")
            if not isinstance(routes, list) or any(not isinstance(route, dict) for route in routes):
                raise DirectionsError()
            valid = [route for route in routes if isinstance(route.get("properties"), dict) and _amount(route["properties"].get("totalTime")) is not None]
            route = min(valid, key=lambda item: item["properties"]["totalTime"], default=None)
            if route is None or not isinstance(route.get("steps"), list):
                raise DirectionsError()
            steps = route["steps"]
        properties = route.get("properties")
        if not isinstance(properties, dict):
            raise DirectionsError()
        distance, seconds = _amount(properties.get("totalDistance")), _amount(properties.get("totalTime"))
    if distance is None or seconds is None:
        raise DirectionsError()
    paths, instructions = _geometry(steps)
    if distance and not paths:
        raise DirectionsError()
    return {"status": "ok", "distance": distance, "seconds": seconds, "paths": paths, "instructions": instructions}


def fetch_directions(mode, points, *, fetcher=None, fetched_at=None):
    if mode not in ENDPOINTS or not isinstance(points, list) or not 2 <= len(points) <= 13:
        raise DirectionsError(400)
    for point in points:
        if not isinstance(point, dict) or set(point) != {"lat", "lng"}:
            raise DirectionsError(400)
        lat, lng = point["lat"], point["lng"]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (lat, lng)) or abs(lat) > 90 or abs(lng) > 180:
            raise DirectionsError(400)
    legs = []
    if all(start == end for start, end in zip(points, points[1:])):
        return {"mode": mode, "legs": [{"status": "ok", "distance": 0, "seconds": 0, "paths": [], "instructions": ["같은 위치예요."]} for _ in points[1:]], "distance": 0, "seconds": 0}
    key = settings.KAKAO_REST_API_KEY
    if not isinstance(key, str) or not key.strip():
        raise DirectionsError(503)
    key = key.strip()
    for start, end in zip(points, points[1:]):
        if start == end:
            legs.append({"status": "ok", "distance": 0, "seconds": 0, "paths": [], "instructions": ["같은 위치예요."]})
            continue
        params = {"origin": f"{start['lng']},{start['lat']}", "destination": f"{end['lng']},{end['lat']}", "summary": "false", "alternatives": "false"} if mode == "car" else {
            "start_x": start["lng"], "start_y": start["lat"], "end_x": end["lng"], "end_y": end["lat"], "input_coord": "WGS84", "output_coord": "WGS84",
        }
        try:
            leg = parse_directions(mode, _get(mode, params, key, fetcher))
            sync_route(mode, start, end, leg, fetched_at=fetched_at)
            legs.append(leg)
        except DirectionsError as exc:
            saved = get_route(mode, start, end)
            leg = dict(route_payload(saved)) if saved else {"paths": [], "instructions": []}
            message = "길찾기 요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요." if exc.status == 429 else f"{mode} 경로 제공자가 요청을 처리하지 못했어요."
            leg.update(status="error", error=message)
            if saved:
                leg.update(stale=True, warning="저장된 이전 경로이며 현재 제공자 조회는 실패했어요.")
            legs.append(leg)
    complete = all(leg["status"] == "ok" for leg in legs)
    return {"mode": mode, "legs": legs, "distance": sum(leg["distance"] for leg in legs) if complete else None, "seconds": sum(leg["seconds"] for leg in legs) if complete else None}
