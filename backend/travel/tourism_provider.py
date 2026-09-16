import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


TOUR_API_URL = "https://apis.data.go.kr/B551011/KorService2/locationBasedList2"
CONTENT_TYPES = ("12", "14", "28")
RADIUS = 2500
PAGE_SIZE = 100
MAX_PAGES = 3
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

STADIUMS = {
    "JAMSIL": ("잠실야구장", "서울특별시 송파구 올림픽로 25", 37.5161987797456, 127.075940589715),
    "GOCHEOK": ("고척스카이돔", "서울특별시 구로구 경인로 430", 37.4982125677913, 126.867088741096),
    "MUNHAK": ("인천 SSG 랜더스필드", "인천광역시 미추홀구 매소홀로 618", 37.4350819826381, 126.690759830613),
    "SUWON": ("수원 KT 위즈 파크", "경기도 수원시 장안구 경수대로 893", 37.2978428909635, 127.011348102567),
    "DAEJEON": ("대전 한화생명 볼파크", "대전광역시 중구 대종로 373", 36.3173370007388, 127.428013823451),
    "DAEGU": ("대구 삼성 라이온즈 파크", "대구광역시 수성구 야구전설로 1", 35.8411289243023, 128.681236372268),
    "GWANGJU": ("광주-KIA 챔피언스 필드", "전남광주통합특별시 북구 서림로 10", 35.1694249627659, 126.888805470329),
    "SAJIK": ("사직야구장", "부산광역시 동래구 사직로 45", 35.194366802896, 129.059900885997),
    "CHANGWON": ("창원 NC 파크", "경상남도 창원시 마산회원구 삼호로 63", 35.2219848625101, 128.579580117268),
}

CULTURE_LABELS = {
    "A02060100": "박물관", "A02060200": "기념관", "A02060300": "전시관",
    "A02060400": "컨벤션센터", "A02060500": "미술관/화랑", "A02060600": "공연장",
    "A02060700": "문화원", "A02060800": "외국문화원", "A02060900": "도서관",
    "A02061000": "대형서점", "A02061100": "문화전수시설", "A02061200": "영화관",
    "A02061300": "어학당", "A02061400": "학교",
}


class TourismProviderError(Exception):
    def __init__(self, code="upstream_unavailable", status=502):
        super().__init__(code)
        self.code = code
        self.status = status


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TourismProviderError("upstream_redirect", 502)


def distance_meters(a_lat, a_lng, b_lat, b_lng):
    rad = math.pi / 180
    h = math.sin((b_lat - a_lat) * rad / 2) ** 2 + math.cos(a_lat * rad) * math.cos(b_lat * rad) * math.sin((b_lng - a_lng) * rad / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def _road_building(address):
    match = re.search(r"\S+(?:로|길)\s+\d+(?:-\d+)?(?=\s|$|,|\()", address)
    return re.sub(r"\s+", " ", match.group(0)) if match else None


def _inside_stadium(title, address, lat, lng, stadium):
    name, stadium_address, s_lat, s_lng = stadium
    if _road_building(stadium_address) == _road_building(address):
        return True
    compact = re.sub(r"\s", "", title)
    if re.search(r"야구장|스카이돔|랜더스필드|위즈파크|볼파크|라이온즈파크|챔피언스필드|NC파크|NC구장", compact, re.I) and not re.search(r"역|사거리|앞점|입구점", compact):
        return True
    return distance_meters(s_lat, s_lng, lat, lng) < 80


def _category(item):
    content_type = item.get("contenttypeid")
    title = item.get("title") if isinstance(item.get("title"), str) else ""
    cat3 = item.get("cat3") if isinstance(item.get("cat3"), str) else ""
    if content_type not in CONTENT_TYPES or re.search(r"(?:19|20)\d{2}.*(?:페어|축제|박람회|페스티벌)", title) or re.search(r"야구장|야구경기장|축구장|종합운동장", title):
        return None
    if re.search(r"야외|실외|물놀이장|수영장", title):
        return None if content_type == "28" else "sight"
    if re.search(r"공원|산책|둘레길|숲길|수목원|생태숲", title) or cat3 == "A03022700":
        return "walk"
    indoor = r"박물관|미술관|전시관|전시실|과학관|문학관|기념관|공연장|극장|영화관|아쿠아리움|수족관|도서관|갤러리|아트홀|보드게임|방탈출|볼링|실내"
    if re.search(indoor, title) or (content_type == "14" and cat3 in {"A02060100", "A02060200", "A02060300", "A02060500", "A02060600", "A02060700"}):
        return "indoor"
    return None if content_type == "28" else "sight"


def _indoor_label(title):
    for pattern, label in ((r"보드게임|보드카페", "보드게임카페"), (r"방탈출", "방탈출카페"), (r"볼링", "볼링장"), (r"영화관", "영화관"), (r"박물관", "박물관"), (r"미술관|갤러리|화랑", "미술관·갤러리"), (r"전시관|전시실", "전시관"), (r"과학관", "과학관"), (r"문학관", "문학관"), (r"기념관", "기념관"), (r"공연장|극장|아트홀", "공연장"), (r"아쿠아리움|수족관", "아쿠아리움"), (r"도서관", "도서관")):
        if re.search(pattern, title):
            return label
    return None


def normalize_item(item, stadium):
    if not isinstance(item, dict):
        return None
    content_id, content_type, title = item.get("contentid"), item.get("contenttypeid"), item.get("title")
    x, y = item.get("mapx"), item.get("mapy")
    if not all(isinstance(value, str) for value in (content_id, title, x, y)) or not content_id.isdigit() or not title.strip() or not x.strip() or not y.strip():
        return None
    try:
        lat, lng = float(y), float(x)
    except ValueError:
        return None
    if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 90 or abs(lng) > 180:
        return None
    address = item.get("addr1", "") if isinstance(item.get("addr1", ""), str) else ""
    name, _, s_lat, s_lng = stadium
    distance = distance_meters(s_lat, s_lng, lat, lng)
    if distance > RADIUS or _inside_stadium(title, address, lat, lng, stadium):
        return None
    kind = _category(item)
    if not kind:
        return None
    category = {"walk": "산책", "sight": "관광 명소", "indoor": "실내 놀거리"}[kind]
    subcategory = CULTURE_LABELS.get(item.get("cat3")) or (_indoor_label(title) if kind == "indoor" else None)
    image = item.get("firstimage", "") if isinstance(item.get("firstimage", ""), str) else ""
    image_url = image.strip() if urlsplit(image.strip()).scheme == "https" and urlsplit(image.strip()).netloc else ""
    return {"placeId": f"tour:{content_id}", "tourContentId": content_id, "contentTypeId": content_type, "name": title.strip(), "lat": lat, "lng": lng, "category": category, "kind": kind, "cuisine": "기타", "address": address.strip(), "phone": item.get("tel", "") if isinstance(item.get("tel", ""), str) else "", "detail": f"{subcategory or category} · 한국관광공사", "distance": distance, **({"subcategory": subcategory} if subcategory else {}), **({"imageUrl": image_url} if image_url else {})}


def _complete_record(item):
    if not isinstance(item, dict) or not all(isinstance(item.get(field), str) and item[field].strip() for field in ("contentid", "contenttypeid", "title", "mapx", "mapy")) or not item["contentid"].isdigit() or item["contenttypeid"] not in CONTENT_TYPES:
        return False
    for field, limit in (("title", 255), ("addr1", 500), ("tel", 120), ("firstimage", 500)):
        if field in item and (not isinstance(item[field], str) or len(item[field]) > limit):
            return False
    try:
        lat, lng = float(item["mapy"]), float(item["mapx"])
    except ValueError:
        return False
    return math.isfinite(lat) and math.isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180


def parse_page(value):
    if not isinstance(value, dict):
        raise TourismProviderError("invalid_upstream_response")
    response = value.get("response")
    header = response.get("header") if isinstance(response, dict) else None
    if not isinstance(header, dict) or header.get("resultCode") not in {"0000", "00"}:
        raise TourismProviderError("upstream_rejected", 503)
    body = response.get("body")
    if not isinstance(body, dict):
        raise TourismProviderError("invalid_upstream_response")
    raw_total = body.get("totalCount")
    if isinstance(raw_total, bool) or not isinstance(raw_total, (int, str)) or isinstance(raw_total, str) and not raw_total.isascii() or isinstance(raw_total, str) and not raw_total.isdigit():
        raise TourismProviderError("invalid_upstream_response")
    total = int(raw_total)
    if total < 0:
        raise TourismProviderError("invalid_upstream_response")
    items = body.get("items")
    if not isinstance(items, dict) and items is not None and items != "":
        raise TourismProviderError("invalid_upstream_response")
    item = items.get("item") if isinstance(items, dict) else None
    if item is not None and not isinstance(item, (dict, list)):
        raise TourismProviderError("invalid_upstream_response")
    result = item if isinstance(item, list) else [item] if isinstance(item, dict) else []
    if total and not result:
        raise TourismProviderError("invalid_upstream_response")
    return result, total


def _read_page(params, service_key, timeout, opener):
    query = urlencode({"serviceKey": unquote(service_key.strip()), "MobileOS": "ETC", "MobileApp": "KBORoute", "_type": "json", **params})
    request = Request(f"{TOUR_API_URL}?{query}", headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"application/json", "text/json"}:
                raise TourismProviderError("invalid_upstream_content_type")
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise TourismProviderError("upstream_response_too_large")
    except TourismProviderError:
        raise
    except HTTPError as error:
        raise TourismProviderError("upstream_rate_limited" if error.code == 429 else "upstream_unavailable", 429 if error.code == 429 else 502) from None
    except (URLError, TimeoutError, OSError):
        raise TourismProviderError() from None
    try:
        return parse_page(json.loads(data))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise TourismProviderError("invalid_upstream_response") from None


def fetch_tourism(stadium_code, lat, lng, service_key, *, timeout=8, opener=None):
    stadium = STADIUMS[stadium_code]
    places, successes, failures, truncated = [], 0, 0, False
    last_error = TourismProviderError()
    opener = opener or build_opener(_RejectRedirects())
    for content_type in CONTENT_TYPES:
        for page in range(1, MAX_PAGES + 1):
            try:
                items, total = _read_page({"mapX": str(lng), "mapY": str(lat), "radius": str(RADIUS), "contentTypeId": content_type, "arrange": "E", "numOfRows": str(PAGE_SIZE), "pageNo": str(page)}, service_key, timeout, opener)
                successes += 1
                for item in items:
                    if not _complete_record(item):
                        failures += 1
                        continue
                    if place := normalize_item(item, stadium):
                        places.append(place)
                if page * PAGE_SIZE >= total:
                    break
                if page == MAX_PAGES:
                    truncated = True
            except TourismProviderError as error:
                last_error = error
                failures += 1
                break
    if failures and not successes:
        raise last_error
    unique = {place["placeId"]: place for place in places}
    result = sorted(unique.values(), key=lambda place: (place["distance"], place["placeId"]))
    return {"status": "partial" if failures and successes else "error" if failures else "ok", "places": result, "truncated": truncated}
