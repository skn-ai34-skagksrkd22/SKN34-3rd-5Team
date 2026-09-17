# baseball — 야구 기준 데이터·공개 조회·관리자 CRUD

야구 구단·구장, 경기·순위, 좌석·예매·구장 안내를 저장하는 Django 앱이다. TVING 관계형 데이터도 이 앱의 모델로 통합되어 있다. HTTP 조회/수정과 LLM용 읽기 전용 SQL은 **서로 다른 접근 경로**다.

## 소스와 경로

- [루트 URL](../../backend/config/urls.py) → [앱 URL](../../backend/baseball/urls.py) → [뷰](../../backend/baseball/views.py) → [직렬화·검증](../../backend/baseball/serializers.py) → [모델](../../backend/baseball/models.py).
- [권한](../../backend/baseball/permissions.py), [CSV 로더](../../backend/baseball/data_loader.py), [SQL 서비스](../../backend/baseball/query_service.py), [SQL 저장소](../../backend/baseball/query_repository.py).
- 아래 경로는 **Django 직접 경로**다. [Nginx](../../nginx/nginx.conf)는 `/api/`를 제거하여 전달하므로 외부에서는 `/api/baseball/...`을 사용한다. [설정](../../backend/config/settings.py)의 OpenAPI 경로에는 `/api`가 삽입되지만 Django URL 자체에는 없다.
- 기본 인증은 JWT `Authorization: Bearer <access-token>`. 공개 API는 `AllowAny`지만 잘못된 토큰을 보내면 인증 단계에서 거절될 수 있다. 관리 API는 인증된 `is_active=True`, `is_staff=True` 사용자만 허용한다.

## 모델과 데이터 흐름

```text
CSV → BaseballDataLoaderV1 → default DB
TVING → tving.service → tving.parsers → tving.relational → 같은 baseball 모델
                                  ↓
공개 GET / 관리자 CRUD ← ORM(default)
LLM 도구 → BaseballQueryService → SQL 검증 → baseball_readonly 연결
```

| 모델 묶음 | 역할·관계 |
| --- | --- |
| `Team`, `Stadium`, `HomeContext` | 구단·구장 및 시즌별 홈구장 연결. `(season, team, stadium)` 유일 |
| `PostseasonStage`, `Game`, `StandingHistory` | 포스트시즌 단계, 홈/원정 경기, 구단별 날짜 순위. `(team, snapshot_date)` 유일 |
| `SeatZone`, `TicketPrice`, `TicketPolicy` | 홈구장별 좌석 구역, 가격, 구단/경기별 예매 정책 |
| `SeatMap`, `SeatMapAsset`, `SeatScope`, `SeatView` | 홈구장별 배치도·이미지, 관람 범위·시야 설명 |
| `Transport`, `FoodStore`, `FoodStoreLocation`, `FoodStoreMenu`, `StadiumContent`, `Facility` | 구장 교통·주차, 매점과 위치/메뉴, 콘텐츠, 편의시설 |
| `TeamProfile`, `TeamSeasonRecord`, `Player`, `PlayerSeasonRecord`, `PlayerCareerRecord`, `TeamRoster`, `TeamTopPlayer` | TVING 구단 프로필·기록, 선수 신원·시즌/통산 기록, 선수단·상위 선수 |
| `ScheduleDay`, `ProviderSnapshot` | 날짜별 경기 목록/완전성 표식, 레거시 정규화 JSON 스냅샷 |

현재 구체 모델은 **28개**, 관리자 router 리소스는 **19개**다. `SyncedRecord`는 추상 모델이다. TVING 확장 모델 9개가 모두 baseball 관리자 router에 노출되는 것은 아니다. 선수/스냅샷의 별도 API는 [tving 문서](tving.md)를 본다.

기본 19개 모델은 명시적인 정수 `id`를 사용한다. 참조 관계는 대부분 `PROTECT`이며, 선수에 연결된 시즌/통산 기록·선수단·상위 선수는 `CASCADE`다. `Game`의 구단/구장/포스트시즌 참조는 nullable이므로 외부 경기의 미확정 구장이나 올스타 팀을 수용한다. TVING 신선도·원천 필드가 모델에 존재해도 아래 CRUD serializer 필드에 없으면 이 API로 읽거나 수정할 수 없다.

[CSV 명령](../../backend/baseball/management/commands/import_baseball_data.py)은 기존 자연키 행을 덮어쓰지 않고 신규 적재한다. `--data-dir`, `--dry-run`, `--report`를 지원하며 오류나 거부 행이 있으면 전체 롤백한다. 로더가 지원하지 않는 외부 장소·비공식 위치 자료 등을 모두 가져오는 기능은 아니다. 실제 수집/적재를 실행해야 데이터가 생기며 README 작성 과정에서는 실행하지 않았다.

## 공개 API — 모두 GET

목록은 기본 `{count, next, previous, results}` 페이지 응답, `page`, `page_size`(기본 30, 최대 100)를 사용한다. 예외는 `/teams/`의 배열 응답과 구장 상세의 객체 응답이다. ID 필터는 코드가 아닌 DB 정수 PK이며 `1..2147483647` 범위의 ASCII 숫자만 허용한다. 날짜는 정확한 `YYYY-MM-DD` 형식이다.

| Django 경로 | 쿼리 필터 | 응답 항목 |
| --- | --- | --- |
| `/baseball/teams/` | 없음 | `id, team_code, team_name_ko` 배열; team_code 순 |
| `/baseball/stadiums/` | `q`: 구장명·주소·홈구단명 부분 검색 | 구장 필드 + `home_teams[]` |
| `/baseball/stadiums/{code}/` | 경로 `code=stadium_code` | 구장 단일 객체; 없으면 404 |
| `/baseball/stadiums/{code}/seat-zones/` | `home_context, team, season` | seat-zones 필드 |
| `/baseball/stadiums/{code}/ticket-prices/` | `home_context, team, season` | ticket-prices 필드 + `seat_zone_code, seat_zone_name` |
| `/baseball/stadiums/{code}/seat-maps/` | `home_context, team, season` | seat-maps 필드 + `assets[]` |
| `/baseball/stadiums/{code}/seat-scopes/` | `home_context, team, season` | seat-scopes 필드 + `seat_views[]` |
| `/baseball/stadiums/{code}/seat-views/` | `home_context, team, season` | seat-views 필드 |
| `/baseball/stadiums/{code}/food-stores/` | 별도 필터 없음 | food-stores 필드 + `locations[], menus[]` |
| `/baseball/stadiums/{code}/transports/` | 별도 필터 없음 | transports 필드 |
| `/baseball/stadiums/{code}/facilities/` | 별도 필터 없음 | facilities 필드 |
| `/baseball/stadiums/{code}/contents/` | 별도 필터 없음 | stadium-contents 필드 |
| `/baseball/games/` | `date_from, date_to, team, stadium, status` | games 필드 |
| `/baseball/standings/` | `snapshot_date` | standing-histories 필드 |
| `/baseball/postseason-stages/` | `date_from, date_to, status` | postseason-stages 필드 |
| `/baseball/ticket-prices/` | `seat_zone, home_context` | ticket-prices 필드 + 좌석 코드/명 |
| `/baseball/ticket-policies/` | `team, game` | ticket-policies 필드 |

- `q`는 앞뒤 공백 제거 후 150자로 자른다. 구장 `home_teams` 원소는 `id, team_id, code, name, season`이다.
- 경기의 양쪽 날짜를 모두 보냈을 때만 역전/366일 초과를 검사한다. 한쪽 날짜만 지정할 수도 있다. `status`는 50자로 자른 `status_code` 정확 일치다.
- 순위 날짜 생략 시 **현재 Team 전체 개수만큼 서로 다른 구단이 있는 최신 날짜**를 선택한다. 완전한 날짜가 없으면 빈 목록이다.
- 포스트시즌은 조회 범위와 단계 기간이 겹치는 행을 반환한다. 역전 기간은 400이며 경기와 달리 366일 제한은 없다. `status`는 `status_tag` 정확 일치다.
- 하위 목록은 구장 존재를 별도 검사하지 않으므로 모르는 `{code}`도 빈 페이지(200)가 된다. 문서에 없는 필터는 구현되지 않았다.
- 공개 baseball GET은 저장 DB만 읽는다. 자동 TVING 갱신이나 별도 경기/선수 상세 HTTP 경로를 이 앱에 가정하면 안 된다.

## 관리자 자동 CRUD — 전체 19개 리소스

[DefaultRouter](../../backend/baseball/urls.py)가 아래 모든 리소스에 동일한 경로를 생성한다. API root는 `/baseball/manage/`다. Django admin 사이트(`/admin/`)와는 별개다.

| 메서드·경로 | 요청 | 성공 응답 |
| --- | --- | --- |
| `GET /baseball/manage/{resource}/` | `q, page, page_size` | 200 페이지 객체 |
| `POST /baseball/manage/{resource}/` | 아래 JSON 필드 | 201 생성 객체 |
| `GET /baseball/manage/{resource}/{pk}/` | 없음 | 200 객체 + `_etag`, `ETag` 헤더 |
| `PATCH /baseball/manage/{resource}/{pk}/` | 변경 필드 + `If-Match` 헤더 또는 `_etag` | 200 수정 객체 + 새 `_etag`, `ETag` |
| `DELETE /baseball/manage/{resource}/{pk}/` | `If-Match` 헤더 또는 `_etag` | 204 본문 없음 |

`PUT`은 **405**이며 PATCH만 지원한다. HEAD/OPTIONS도 허용 메서드에 포함된다. 목록은 PK 순이며 `q`로 해당 모델의 CharField/TextField 전체를 OR 부분 검색한다(ASCII 숫자이면 PK 일치도 OR). FK 이름 검색이나 리소스별 공개 필터가 관리자 목록에 자동 적용되지 않는다.

다음 표가 실제 `RESOURCE_FIELDS` 계약이다. **POST는 nullable 열을 제외한 필드를 제공**한다. nullable 필드는 생략/null 허용, PATCH는 변경 필드만 제공한다. 모든 `*_id`는 존재하는 관련 객체의 PK다. 날짜/시간/일시는 각각 ISO 날짜·시간·일시, 금액/횟수/ID는 정수, `accessible`·`reservation_required`는 불리언, 좌표·승차는 decimal, 나머지는 모델의 문자열 필드다. 정밀한 길이·유일성·타입 제약은 [모델](../../backend/baseball/models.py)과 [serializer](../../backend/baseball/serializers.py)가 기준이다.

| resource | 모델 | 요청·응답 필드 | nullable/생략 가능 |
| --- | --- | --- | --- |
| `teams` | `Team` | `id`, `team_code`, `team_name_ko` | — |
| `stadiums` | `Stadium` | `id`, `stadium_code`, `stadium_name_ko`, `address`, `longitude`, `latitude`, `geocode_source`, `facility_manager`, `game_operator`, `phone_general`, `phone_facility`, `phone_ticket`, `collected_at` | `facility_manager`, `game_operator`, `phone_general`, `phone_facility`, `phone_ticket` |
| `home-contexts` | `HomeContext` | `id`, `season`, `team_id`, `stadium_id` | — |
| `postseason-stages` | `PostseasonStage` | `id`, `stage_code`, `stage_name`, `start_date`, `end_date`, `matchup_description`, `status_tag`, `collected_at` | — |
| `games` | `Game` | `id`, `game_code`, `home_team_id`, `away_team_id`, `stadium_id`, `postseason_stage_id`, `game_date`, `game_time`, `home_score`, `away_score`, `status_code`, `game_type`, `collected_at` | `home_team_id`, `away_team_id`, `stadium_id`, `postseason_stage_id`, `home_score`, `away_score` |
| `standing-histories` | `StandingHistory` | `id`, `team_id`, `snapshot_date`, `rank`, `wins`, `losses`, `draws`, `games_behind`, `collected_at` | — |
| `seat-zones` | `SeatZone` | `id`, `home_context_id`, `zone_code`, `zone_name_ko`, `level`, `side`, `seat_type`, `group_size`, `accessible` | `group_size`, `accessible` |
| `ticket-prices` | `TicketPrice` | `id`, `seat_zone_id`, `price_tier`, `day_type`, `customer_type`, `group_size`, `price_krw`, `valid_from`, `valid_to`, `discount_condition`, `collected_at` | `group_size`, `valid_from`, `valid_to` |
| `ticket-policies` | `TicketPolicy` | `id`, `policy_code`, `team_id`, `game_id`, `policy_type`, `subtype`, `open_at`, `max_tickets`, `channel_no`, `booking_channel`, `channel_condition`, `collected_at` | `game_id`, `open_at`, `max_tickets` |
| `seat-maps` | `SeatMap` | `id`, `home_context_id`, `map_title`, `page_url` | — |
| `seat-map-assets` | `SeatMapAsset` | `id`, `seat_map_id`, `asset_no`, `asset_url`, `asset_role` | — |
| `seat-scopes` | `SeatScope` | `id`, `home_context_id`, `scope_code`, `scope_name` | — |
| `seat-views` | `SeatView` | `id`, `seat_scope_id`, `view_characteristic`, `roof_coverage`, `evidence_scope` | — |
| `food-stores` | `FoodStore` | `id`, `record_code`, `stadium_id`, `store_facility`, `location_qty`, `collected_at` | `location_qty` |
| `food-store-locations` | `FoodStoreLocation` | `id`, `food_store_id`, `location_no`, `floor`, `zone_location` | — |
| `food-store-menus` | `FoodStoreMenu` | `id`, `food_store_id`, `menu_category_official` | — |
| `transports` | `Transport` | `id`, `stadium_id`, `access_code`, `mode`, `title`, `details`, `parking_spaces`, `reservation_required`, `collected_at` | `parking_spaces`, `reservation_required` |
| `stadium-contents` | `StadiumContent` | `id`, `record_code`, `stadium_id`, `content_type`, `name`, `floor`, `location`, `official_description`, `operating_condition`, `collected_at` | — |
| `facilities` | `Facility` | `id`, `record_code`, `stadium_id`, `facility_type`, `floor`, `side`, `nearby_section`, `gate`, `gender`, `indoor_outdoor`, `location_detail`, `collected_at` | — |

### 검증·동시 수정·오류

- 생성 `id`는 1 이상이고 수정 시 변경 불가. 홈팀/원정팀은 서로 달라야 한다.
- 점수, 승/패/무, 순위, 그룹 인원, 가격, 최대 매수, 채널/자산/위치 번호, 주차면수는 음수 불가. 이 검사를 모든 정수 필드에 확대 해석하지 않는다.
- 시작일≤종료일, 가격 유효 시작일≤종료일. 경도 ±180, 위도 ±90. `page_url`, `asset_url`은 http/https URL만 허용한다.
- 수정/삭제 직전에 상세 GET의 따옴표 포함 ETag를 보낸다. ETag는 serializer 표현의 SHA-256 해시이며 숨겨진 모델 필드 전체의 버전이 아니다. 쓰기는 트랜잭션/행 잠금으로 처리한다.
- 처리되는 DRF 오류는 `{code, message, field_errors}`로 정규화한다. 삭제 참조 충돌은 `references: {모델 표시명: 건수}`도 포함한다.

| 상태 | 조건 |
| --- | --- |
| 400 | 필드·필터 검증 실패, 잘못된 FK/유일값 serializer 검증, If-Match 누락 |
| 401 / 403 | JWT 인증 실패 / 관리자 권한 부족 |
| 404 | 상세 없음 또는 유효하지 않은 페이지 |
| 405 | 허용하지 않는 메서드 |
| 409 `conflict` | 저장 시 DB 무결성 충돌 |
| 409 `protected` | 다른 행이 참조하여 삭제 불가 |
| 412 `stale_write` | ETag 불일치 |

예상하지 못한 서버 예외까지 이 JSON 형식으로 보장하는 전역 오류 처리기는 아니다.

## 읽기 전용 SQL — HTTP 엔드포인트가 아닌 내부 서비스

[LLM 채팅 서비스](../../backend/llm/chat_service.py)가 도구를 통해 사용한다. `get_baseball_schema()`는 `{schema, tables:[{name, quoted_name, columns}]}`를 제공하고 `execute_baseball_select(sql, params=None, max_rows=100)`는 `{columns, rows, truncated}`를 반환한다. `rows`는 열 순서에 맞춘 배열이며 decimal/날짜는 Django JSON 변환을 거친다.

- [서비스](../../backend/baseball/query_service.py)는 sqlglot PostgreSQL AST로 단일 조회를 검사한다. 실제 baseball 모델 테이블을 최소 하나 참조해야 하며 **테이블명은 큰따옴표로 인용**, 스키마는 생략 또는 `public`만 허용한다. 일반 비재귀 CTE/서브쿼리는 검사 범위 내에서 가능하다.
- DDL/DML, 다중 문장, SELECT INTO, 잠금, 재귀 CTE, FROM ONLY, 명시적 PostgreSQL 연산자, 사용자 정의/객체 식별자 타입, 스키마 지정 함수 및 허용 목록 밖 함수는 거부한다. SQL 전체 문법을 제공하는 범용 DB 콘솔이 아니다.
- `params`는 dict, placeholder는 `%(name)s` 형태의 named parameter다. 문자열 보간으로 값을 붙이지 않는다.
- [저장소](../../backend/baseball/query_repository.py)는 `baseball_readonly` 별도 계정과 `SET TRANSACTION READ ONLY`, `search_path=pg_catalog, public`, 문장/잠금 시간 제한을 사용한다. 결과를 `max_rows+1`개까지만 가져와 초과 여부를 판정하고 응답 바이트 제한도 적용한다.
- [설정 기본값](../../backend/config/settings.py): 최대 행 200, SQL 32768 bytes, 응답 1 MiB, 문장 3000 ms, 잠금 대기 1000 ms. `max_rows` 기본 요청값은 100이다. 환경 변수로 바뀔 수 있으며 실제 배포값을 확인한 것은 아니다.
- 결과 크기 제한으로 잘린 경우 `truncated=true`; 컬럼 자체나 첫 행부터 너무 크면 예외. 별도의 SQL 결과 페이지/커서는 제공하지 않는다. 행 제한은 비싼 집계·조인 비용이나 DB 메모리 사용량까지 보장하지 않는다.
- 검증 오류, 계정 미설정, 실행/권한 오류, 문장/잠금 timeout, 결과 과대 예외는 Python 예외이며 이 앱 HTTP 상태로 직접 매핑되지 않는다.

**허용 범위는 19개 router 리소스가 아니라 현재 baseball 앱의 구체 모델 전체(28개)**다. 새 모델 추가 시 자동 확대되므로 스키마와 권한을 함께 검토해야 한다. [계정 준비 명령](../../backend/baseball/management/commands/provision_baseball_reader.py)의 help에 남은 “19개”와 달리 실제 테이블 목록은 동적이다. 계정 권한을 실제 프로비저닝해야 DB 수준 제한이 성립한다. 이 명령은 위험한 역할 속성·PUBLIC/default ACL을 검사하며 `--prepare-db-permissions`는 PUBLIC TEMP 권한을 바꾸므로 일반 조회 명령이 아니다. [DB router](../../backend/baseball/db_router.py)는 readonly alias의 migration만 막고, 모든 ORM을 읽기 전용으로 만드는 장치가 아니다.

## 확인 범위

[API 테스트](../../backend/baseball/tests/test_api.py), [SQL 검증 테스트](../../backend/baseball/tests/test_query_service.py), [SQL 저장소 테스트](../../backend/baseball/tests/test_query_repository.py)가 관련 회귀 근거다. 이 문서는 현재 소스와 로컬 링크를 정적으로 확인한 결과이며 DB 접속·마이그레이션·실제 외부 호출·API 실행 성공을 주장하지 않는다.
