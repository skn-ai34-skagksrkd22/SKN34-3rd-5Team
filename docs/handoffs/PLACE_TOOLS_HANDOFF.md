# 장소 서비스 호출 인계

LLM 바인딩 없이 `travel.place_service.PlaceService` 또는 아래 함수를 Django 내부에서 직접 import한다.

```python
from travel.place_service import (
    create_place, list_places, get_place, update_place, delete_place,
    search_and_sync_places,
)
```

- 공개 호출: `list_places(filters, page=1, page_size=20)`, `get_place(id)`, `search_and_sync_places(query)`
- 신뢰된 관리자 호출: `create_place(data, actor=request.user)`, `update_place(id, changes, actor=request.user)`, `delete_place(id, actor=request.user)`. `actor`는 인증·활성·staff 조건을 모두 충족해야 하며 외부 입력의 Boolean 권한값으로 대체하지 않는다.
- 검색 입력: `method`(`keyword`/`category`), `keyword?`, `category?`, `lat`, `lng`, `radius?`, `page`(1~3), `size`(1~15), `sort`(`accuracy`/`distance`). category는 `FD6/CE7/AT4/CT1/CS2/AD5`만 허용한다.
- 검색 반환: `{"places": [...], "hasNextPage": bool, "syncedAt": ISO-8601}`. `syncedAt`은 공급자 조회 성공 시각이며 모든 DB 행의 저장 최신성을 뜻하지 않는다. 장소의 `id`는 내부 PK가 아니라 카카오 ID이고 `x/y`는 기존 문자열 형식이다.
- CRUD의 `id`는 내부 DB PK다. PATCH에서 내부 ID, `kakao_place_id`, `created_at`, `updated_at`, `last_synced_at`은 변경할 수 없다.
- 검색은 원격 응답 전체 검증 후 한 transaction에서 현재 페이지를 처리한다. 같은 카카오 ID 행의 `last_synced_at`이 조회 성공 시각 기준 `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS`(기본 600초) 이내면 정확한 경계 또는 미래 시각도 포함해 모든 DB 쓰기를 건너뛰고, 없거나 null이거나 간격을 초과한 행만 생성·갱신한다. 이 공급자 중립 Django 설정은 양의 정수(초)만 허용하며 잘못된 값이면 서버 시작을 실패시킨다. 빈 결과는 기존 행을 삭제하지 않으며 저장 실패는 성공으로 반환하지 않는다.

```python
query = {"method": "keyword", "keyword": "잠실야구장", "lat": 37.5122, "lng": 127.0719, "page": 1, "size": 15, "sort": "distance"}
page = search_and_sync_places(query)
created = create_place({"name": "수동 장소", "address": "서울 송파구", "lat": 37.5, "lng": 127.1}, actor=request.user)
updated = update_place(created["id"], {"phone": "02-123-4567"}, actor=request.user)
delete_place(updated["id"], actor=request.user)
```

```sh
curl -sS http://localhost/api/places/search/ -H 'Content-Type: application/json' \
  --data '{"method":"category","category":"FD6","lat":37.5122,"lng":127.0719,"radius":2000,"page":1,"size":15,"sort":"distance"}'
curl -sS http://localhost/api/places/ -H 'Authorization: Bearer <staff-jwt>' -H 'Content-Type: application/json' \
  --data '{"name":"수동 장소","address":"서울 송파구","lat":37.5,"lng":127.1}'
curl -sS 'http://localhost/api/places/?name=수동&page=1&page_size=20'
```

정상 검색은 `{"places":[{"id":"카카오 ID","place_name":"...","x":"127.0719","y":"37.5122",...}],"hasNextPage":false,"syncedAt":"..."}` 형식이다. HTTP 오류는 모두 `{"error":"안전한 메시지"}`이며 입력 400, 비로그인 401, 비관리자 403, 없음 404, 중복 409, 본문 초과 413, 비 JSON 415, 로컬 동시/분당 제한 429, 카카오 실패 502, 키 미설정·DB 장애 503으로 구분한다. 직접 호출은 `PlaceValidationError`, `PlaceAuthorizationError`, `PlaceNotFoundError`, `PlaceConflictError`, `PlaceRateLimitError`, `PlaceUpstreamError`, `PlaceConfigurationError`를 구분한다.

수동 변경한 카카오 필드는 10분 동기화 간격이 지난 검색에서 원본 값으로 덮어써질 수 있고, 삭제한 카카오 장소도 검색 시 재생성될 수 있다. `updated_at`은 실제 저장 시각, `last_synced_at`은 해당 행을 카카오 값으로 실제 갱신한 시각이며, 건너뛴 행에서는 둘 다 바뀌지 않는다. 영구 차단, 필드 잠금, 캐시, 전국 배치, LLM/RAG 등록은 현재 범위가 아니다.

카카오 정책 확인 기준은 [Developer Site Policies](https://developers.kakao.com/terms/ko/site-policies)와 [Developer Site Terms](https://developers.kakao.com/terms/ko/site-terms)다. 현재 구현은 검색 시 최신화만 제공하며 무기한 보관이나 LLM로의 데이터 이전 권리를 보장하지 않는다.

검색 제한은 프로세스당 동시 8건·분당 240건이며 HTTP는 클라이언트 식별 제한을 한 번 더 적용한다. 현재 `NUM_PROXIES=1`은 신뢰된 단일 Nginx 배치를 전제로 하므로 프록시 토폴로지가 달라지면 먼저 조정하고, 여러 backend worker에 걸친 전역 제한이 실제로 필요해질 때 공유 limiter를 도입한다.
