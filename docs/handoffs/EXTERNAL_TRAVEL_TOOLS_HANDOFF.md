# 외부 여행 데이터 도구 통합 인계

## 이 checkout의 범위

- 브랜치: `Seongho-haru/feat-external-travel-backend` (기준 `707699f`)
- 구현: Kakao 자동차·도보·대중교통 길찾기와 typed `DirectionsRoute` ORM 저장/조회/관리 service
- 제외: TourAPI provider/UI, KMA 날씨, LLM 연결, 공유 설정·URLConf·OpenAPI 파일

## 통합할 공유 설정과 URL

`backend/config/settings.py`:

```python
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
EXTERNAL_DATA_SYNC_INTERVAL_SECONDS = positive_int_env(
    "EXTERNAL_DATA_SYNC_INTERVAL_SECONDS", 600
)
```

`backend/travel/urls.py`:

```python
from .views import DirectionsView

urlpatterns += [
    path("travel/directions/", DirectionsView.as_view(), name="travel-directions"),
]
```

`backend/config/urls.py`는 이미 루트에 `travel.urls`를 include하므로 변경하지 않습니다. 브라우저 계약은 generic Nginx가 `/api/`를 제거하는 `POST /api/travel/directions/`입니다.

## HTTP 계약

요청은 JSON 객체이며 `mode`는 `walk|car|transit`, `points`는 유한한 위도·경도 객체 2~13개입니다. 호환용 `action`은 생략하거나 문자열 `directions`만 허용합니다.

```json
{"mode":"walk","points":[{"lat":37.5,"lng":127.1},{"lat":37.6,"lng":127.2}]}
```

응답은 기존 `CourseDirections`를 보존합니다. 각 leg는 `status`, `paths`, `instructions`와 성공 시 실제 provider `distance`/`seconds`를 가지며, 한 leg라도 실패하면 최상위 `distance`와 `seconds`는 `null`입니다. 같은 좌표 leg는 provider를 호출하지 않고 0을 반환합니다. provider 실패 때 저장 행이 있으면 해당 leg는 `status:error`, `stale:true`, `warning`을 포함하므로 이전 geometry를 현재 성공처럼 표시하지 않습니다.

OpenAPI 반영 항목은 `/api/travel/directions/` POST, request의 `mode` enum과 `points` 2..13/lat -90..90/lng -180..180, 그리고 응답의 nullable totals와 per-leg `ok|error`입니다.

## DirectionsRoute ORM API

`travel.directions_service`:

- `sync_route(mode, start, end, payload, *, fetched_at=None)`
- `get_route(mode, start, end)`
- `list_routes(*, mode=None, min_distance=None, max_distance=None, limit=50)`
- `replace_route(*, actor, mode, start, end, payload)`
- `delete_route(*, actor, route_id)`

좌표는 Decimal 소수점 6자리로 canonicalize되고 `mode + ordered endpoints`가 unique identity입니다. 거리·시간은 실제 provider 값만 저장하며 geometry/instructions만 bounded JSON 배열입니다. 명시적 refresh마다 외부 요청은 수행하되 missing/null/stale(설정 간격 초과) 행만 잠금 갱신하고 exact/future fresh 행에는 UPDATE가 없습니다. public get/list는 DB-only이고, replace/delete는 인증된 active staff actor만 허용하며 수동 replace는 기존 timestamp를 보존하고 새 행은 timestamp를 null로 둡니다.

`0007_directionsroute`는 유효한 legacy directions snapshot만 insert-only로 backfill합니다. 반복 실행해도 typed identity당 한 행이고, 알 수 없거나 잘못된 legacy 행은 삭제·수정하지 않습니다. Tour의 후속 `0008_tourismplace`는 이 migration에 의존합니다.

## Legacy 공용 스냅샷 API

`travel.external_snapshot_service`:

- `sync_snapshot(kind, key, request, payload, *, fetched_at=None)`
- `get_snapshot(kind, key)`
- `list_snapshots(*, kind=None, text="", limit=50)`
- `replace_snapshot(*, actor, kind, key, request, payload)`
- `delete_snapshot(*, actor, snapshot_id)`

kind는 `directions|tourism`만 지원하지만 신규 routing/Tour primary 저장 경로로 사용하지 않습니다. 기존 데이터 검증과 0007 backfill 호환을 위해 남아 있으며 provider 종류별 normalized request/payload만 허용합니다.

`replace_snapshot`/`delete_snapshot`은 인증된 active staff actor만 실행됩니다. 수동 overwrite는 기존 `fetched_at`/`last_synced_at`을 보존하고, 새 행은 두 timestamp를 null로 남깁니다. 삭제 뒤 다음 성공 refresh는 행을 재생성합니다. `get_snapshot`/`list_snapshots`은 DB-only이며 외부 호출이나 timestamp 변경이 없습니다.

## 공급자와 보안 경계

- 자동차: `https://apis-navi.kakaomobility.com/v1/directions`
- 도보: `https://dapi.kakao.com/v2/routing/walk`
- 대중교통: `https://dapi.kakao.com/v2/routing/publictraffic`

host/path는 코드 상수만 사용하고 redirect를 따르지 않습니다. timeout 10초, JSON content type, 2 MB 응답 상한, 전역 동시 provider 슬롯 3개를 적용합니다. URL·키·외부 오류 전문은 응답하지 않습니다. 도보/대중교통 및 일부 자동차 API는 앱 권한/제휴 상태에 따라 거절될 수 있으며 fallback 경로나 속도 추정은 만들지 않습니다.

## 검증과 실행 환경

- Python 3.12.14, Django 6.1.1, DRF 3.18.0, `pgvector/pgvector:pg18`
- `travel.test_external`: 14/14 통과 (실제 PostgreSQL 0007 migration/backfill 반복·legacy 보존, typed unique/concurrency/CRUD, null/fresh/exact/stale/future/no-fresh-UPDATE, poison 방지, parser geometry, HTTP validation/redirect·429 경계)
- 기존 `travel.tests travel.test_settings`: 18/18 통과
- frontend 영향 테스트: 9/9 통과
- Next 16.3.4 production build: 통과
- 허가된 루트 `.env`의 Kakao 키를 stdin으로만 전달한 typed 저장 경로 실제 호출: `car` 성공 944 m/249초/경로 3개, `walk` 성공 1195 m/1223초/경로 14개, `transit` 성공 1815 m/1309초/경로 1개. 모두 `stored:true`, stale 아님이며 fallback 추정은 사용하지 않았습니다.
- 유지 중인 격리 환경: DB `external-travel-db-test` (`127.0.0.1:18875`, 0007 적용), Django `external-travel-backend-test` (`127.0.0.1:18075`). live 검증은 이 컨테이너 안의 새 Python 프로세스로 수행했으며 기존 runserver 프로세스는 typed 변경 전 시작됐으므로 HTTP 재검증 전 coordinator가 재시작해야 합니다.

## 최종 delta와 SHA-256

| 상태 | 파일 | SHA-256 |
| --- | --- | --- |
| M | `backend/travel/models.py` | `eab9cedb8c8d1113b4dfc0dbd38fd70710ffcca09d3b23e4cd54eaaeb5ddcdec` |
| A | `backend/travel/directions_models.py` | `4ceafd165b19366b53c017344b0bd7ab950af51fb5d7d0b1e8b19f28e459061e` |
| A | `backend/travel/directions_service.py` | `5f49fb8824411b4f5567c531b17801895ec2f351bb2acf931f7d1969771df25e` |
| M | `backend/travel/serializers.py` | `81964e7e892640c408c80ad8442803f6976683c61b9663795b2803e627e545cc` |
| M | `backend/travel/views.py` | `9f480c7702aae596e87b7e02beb1558479bed8e9069d9566d65e818769ec2645` |
| A | `backend/travel/directions_provider.py` | `edb791c203f668cc3c77485c6ef26177f00aa3dded2a538bc0058bdca7714ada` |
| A | `backend/travel/external_snapshot_service.py` | `8064842af50362b4767b7998fbf21073b7d85f3a2ea31349606bf90cb1ae65ac` |
| A | `backend/travel/external_test_settings.py` | `c0ff0943de6b3bab045187d2d870b2c617cd5b5cef6fd136d48cc0bd97d1e435` |
| A | `backend/travel/external_test_urls.py` | `3eb0577e510c61c4816d6307ce9c3bb4d27c9f3360342c64d5dad44c376e5337` |
| A | `backend/travel/migrations/0006_externalprovidersnapshot.py` | `56a8f261dfdc40354ed90c6985d2b52f7655a70e9a7ce9c89956a766423a5325` |
| A | `backend/travel/migrations/0007_directionsroute.py` | `93d2cd7ea9a3a3aec44322c984663a9f2cab819753aa46e3057672b7d19ce307` |
| A | `backend/travel/test_external.py` | `ab9677484b4962c418c09350ce353188180efe6616aa8d37169d57af4839dcb2` |
| M | `frontend/app/directions-api/route.ts` | `ad002bef1e0a230ef8dda2b09fd2dcc7e6dea9c599c26c111eccacfc2afa8622` |
| M | `frontend/components/course-travel.tsx` | `a50aecc9f78b961f186de051be6c4016b2f32cda571482daf93b4544dfd5f08c` |
| M | `frontend/docs/COURSE_DIRECTIONS.md` | `85f3c687af5bd54fb7a32b48430b9c090d47c8ce2cf376575c560c39b93d1a13` |
| D | `frontend/lib/course-directions-server.ts` | 기존 파일 `3aac8dd5107ee675a6616633922806ebe7965b98d7d1208dac17a25e28286aa1` |
| M | `frontend/tests/course-directions.test.mjs` | `682a303b4cf4c2366c18b1b6a3e9ed50476af5fe21884c074798cbe0a30171d8` |
| M | `frontend/tests/directions-api-route.test.mjs` | `4f6421d7d834cd9ad8f1507c3746f7df0b3ca5e43d4c554760f6bfbb3fbaa346` |

이 보고서 파일 자체는 self-referential hash가 되므로 목록에서 제외했습니다.
