# TourAPI Django/ORM 이관 핸드오프

## 통합 스니펫

공유 파일은 이 브랜치에서 수정하지 않고 통합 소유자가 아래만 반영합니다.

`backend/travel/models.py` 마지막:

```python
from .tourism_models import TourismPlace  # noqa: E402,F401
```

같은 shared model state에서 `Place.phone`은 0009와 맞게 `models.CharField(max_length=120, blank=True)`입니다. 기존 `PlaceWriteSerializer.phone`의 50자 제한은 그대로 둡니다.

`backend/config/settings.py`:

```python
TOUR_API_KEY = os.getenv("TOUR_API_KEY", "")
EXTERNAL_DATA_SYNC_INTERVAL_SECONDS = positive_int_env("EXTERNAL_DATA_SYNC_INTERVAL_SECONDS", 600)

# REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
"tourism": "20/minute",
```

`backend/travel/urls.py`:

```python
from .tourism_views import TourismSearchView

urlpatterns += [path("tourism/", TourismSearchView.as_view(), name="tourism-search")]
```

`backend/config/urls.py`는 이미 `travel.urls`를 루트에 include합니다. 기존 Nginx `/api/` prefix strip을 거쳐 브라우저는 `GET /api/tourism/?stadium=JAMSIL&lat=...&lng=...`, Django는 `GET /tourism/`입니다. OpenAPI와 `frontend/lib/api/schema.d.ts`는 URL 통합 뒤 기존 생성 명령으로 갱신합니다. 금지 범위인 `frontend/README.md`와 기존 `frontend/docs/NEARBY_PLANNER.md`의 Next BFF/키 설명도 통합 소유자가 Django 경로로 갱신해야 합니다.

## 모델 재사용 계약

재사용하는 기존 모델은 local `develop` `ae09080`의 `travel.models.Place`입니다. 관광지의 `name`, `address`, `lat`, `lng`, `phone`, canonical `url`은 Place에만 저장합니다. 기존 Kakao ID/분류/동기화 필드와 CRUD 계약은 그대로 유지합니다.

진짜 새 관계만 `travel.tourism_models.TourismPlace` OneToOne extension으로 둡니다. extension에는 provider `content_id` unique, `content_type(12|14|28)`, 관광 `category(walk|sight|indoor)`, 선택적 `image_url`, 독립된 관광 `fetched_at`/`last_synced_at`만 있습니다. 공통 장소 필드와 whole-query JSON을 중복 저장하지 않습니다.

검색은 요청마다 provider를 호출하며 성공/partial/truncated 응답의 완전 검증된 엔티티만 한 transaction에서 content ID 정렬 순으로 잠급니다. 새/null/strictly-old 관광 extension만 Place와 함께 갱신하고 정확한 경계·미래 시각은 UPDATE와 timestamp sliding이 없습니다. 관광 갱신은 `Place.last_synced_at`을 절대 변경하지 않습니다. 명시적으로 Kakao ID가 연결된 Place는 관광 metadata timestamp만 갱신하고 공통 필드를 덮어쓰지 않습니다. 이름·거리 또는 같은 숫자 ID로 provider 간 Place를 합치지 않으며 응답에서 사라진 행도 삭제하지 않습니다.

## Migration graph와 데이터 보존

- routing branch: `0006_externalprovidersnapshot -> 0007_directionsroute -> 0008_tourismplace`
- develop Place branch: `0006_place`
- owned merge+transition: `0009_tourismplace_use_common_place`, dependencies `0008_tourismplace`와 `0006_place`

이미 적용된 0008 standalone draft를 고치거나 지우지 않습니다. 0009가 canonical `Place.phone`을 120자로 넓혀 기존 Tour 허용 범위를 무손실 수용하고(nullable OneToOne 추가 전), 각 draft를 **새 `kakao_place_id=NULL` Place**로 복사한 뒤 required로 바꾸고 중복 `name/address/latitude/longitude/phone/source_url` 및 좌표 constraint를 제거합니다. 기존 Kakao write serializer는 50자 제한을 유지하므로 기존 HTTP 계약은 바뀌지 않습니다. 기존 Kakao Place는 건드리지 않고, content ID와 Kakao ID가 같은 숫자여도 병합하지 않습니다. 0008의 legacy snapshot backfill은 완전 검증 가능한 행만 insert-only이며 legacy snapshot을 삭제하거나 필드를 추론하지 않습니다.

## 공개 응답과 callable

공개 검색 응답은 기존 `status`, `places`, `truncated`를 보존하고 실제 provider 완료 시각 `fetchedAt`, 관측 엔티티 중 최신 DB 시각 `lastSyncedAt`, `stale=false`를 추가합니다. 키 미설정은 `unconfigured`; 입력 오류 400; 제한 429; provider business 거절 503; 전송/redirect/content-type/JSON/크기 오류는 credential 없는 502입니다.

LLM 등록은 담당 작업에서 별도로 수행합니다. callable은 다음과 같습니다.

- `external_tourism_search(arguments)`: 공개 provider 검색, `stadium`, `lat`, `lng`만 허용
- `list_tourism_places(arguments)`: DB-only; `page`, `pageSize<=100`, `q`, `category`, `minLat/maxLat/minLng/maxLng`
- `get_tourism_place(content_id)`: DB-only content ID 상세
- `create_tourism_place`, `update_tourism_place`, `delete_tourism_place`: authenticated+active+staff 전용 Place+extension DB 변경; update/delete row lock, manual 변경은 provider timestamps를 만들거나 이동하지 않음

재사용 목록은 `Place`, develop의 기존 Place serializers/service/views/CRUD, routing의 `ExternalProviderSnapshot`과 `DirectionsRoute` migration graph입니다. 새 모델은 기존 모델로 표현할 수 없었던 관광 provider identity/provenance relation인 `TourismPlace` extension 하나뿐입니다. `DirectionsRoute`는 사용자 저장 코스인 `Course`/`CourseStop`과 의미가 달라 routing 소유 모델을 그대로 사용합니다.

## 격리 검증

- 이미지: `skn34-3rd-5team-backend:latest` (`d6ffc210ebfb`), `pgvector/pgvector:pg18` (`2ba9ca5f2e7d`)
- 런타임: Python 3.12.14, Django 6.1.1, DRF 3.18.0, psycopg 3.3.5, PostgreSQL 18.6, Node 22.22.0, npm 10.9.4, Next 16.3.4
- 격리 환경: project label/network `tourapi-test`; DB `127.0.0.1:18876`, HTTP `127.0.0.1:18076`; coordinator 확인을 위해 실행 유지
- backend: `travel.test_tourism` PostgreSQL 13/13, dual-0006 graph부터 `0009`까지 migration/reverse/transition, 80자 legacy phone과 existing Kakao+draft preservation, concurrent new upsert/opposite page lock order, new/fresh/exact/stale/future/null/override120/no-UPDATE/mixed batch, partial/truncated entity write, absence 보존, rollback/CRUD/auth/HTTP/provider 경계 통과; 실제 키가 빈 persistent container에서도 test별 fixture override로 13/13
- borrowed old Kakao regression: existing Place service CRUD, search sync, public/staff API 3/3 통과
- migration state: `makemigrations travel --check --dry-run` 변경 없음
- frontend: focused Node 14/14, focused ESLint, Next production build 통과
- local DB/HTTP repeat: 같은 Tour content ID를 두 번 동기화해 Place 수 `3 -> 3`, 해당 extension 1행; 같은 숫자 Kakao ID의 Place와 Tour Place는 서로 다른 PK; Tour Place의 `Place.last_synced_at=None`, 관광 extension만 `01:10:01` 갱신. `GET :18076/tourism/`은 200 `unconfigured`, HTTP places 0
- live provider: 기존 `TOUR_API_KEY`를 파일/로그/URL에 출력하지 않고 stdin 메모리로만 주입했으나 provider가 `upstream_unavailable`로 거절했습니다. 실서비스 데이터 성공 증거는 없습니다.

## 테스트 의존성 (deliverable 아님)

격리 migration과 기존 CRUD 검증에 routing 및 develop Place 작업물을 복사했습니다. 통합은 각 소유자 원본을 사용하고 아래 파일을 TourAPI delta로 복사하지 않습니다.

- `backend/travel/external_snapshot_service.py` `8064842af50362b4767b7998fbf21073b7d85f3a2ea31349606bf90cb1ae65ac`
- `backend/travel/models.py` `eab9cedb8c8d1113b4dfc0dbd38fd70710ffcca09d3b23e4cd54eaaeb5ddcdec`
- `backend/travel/migrations/0006_externalprovidersnapshot.py` `56a8f261dfdc40354ed90c6985d2b52f7655a70e9a7ce9c89956a766423a5325`
- `backend/travel/directions_models.py` `4ceafd165b19366b53c017344b0bd7ab950af51fb5d7d0b1e8b19f28e459061e`
- `backend/travel/migrations/0007_directionsroute.py` `93d2cd7ea9a3a3aec44322c984663a9f2cab819753aa46e3057672b7d19ce307`
- `backend/travel/migrations/0006_place.py` 및 `place_serializers.py`, `place_service.py`, `place_views.py`, `test_places.py`: local develop `ae09080` 원본
- `backend/travel/models.py`: routing dependency와 develop Place를 격리 테스트에서만 합성; 통합 소유자가 canonical 공유 파일에 두 import를 반영

ORM redirect 직전 credential-free tracked delta SHA-256는 `76d1026e2747333b6cf94e0fbdf115546594a79eb7b5dad91db4c7018c5ac906`이며 이전 per-file manifest는 worker transcript에 남겼습니다.

## 최종 TourAPI deliverable SHA-256

| 상태 | 파일 | SHA-256 |
| --- | --- | --- |
| A | `backend/travel/migrations/0008_tourismplace.py` | `8ee3c355e19f34f3df915361dc38fb3a51efcaa4e3ca2b32ce2ec33c53b605f6` |
| A | `backend/travel/migrations/0009_tourismplace_use_common_place.py` | `b1cb483d9359d4189a9f4c24c929b7ffe73f92540f0c3b0fc1307972dfcff54a` |
| A | `backend/travel/test_tourism.py` | `ff355224d967a1c861156f5a5e4beeb1bf2b05f680b9d96e786e4fc6c0bdb707` |
| A | `backend/travel/tourism_models.py` | `dda61310853a54a540984e10d9fa26369b70f142cc8622a0c8f637c48d4072a8` |
| A | `backend/travel/tourism_provider.py` | `91689ba04e43998dafa1a46bf64bb537ebe83af4a15e7576d278d2ef6fd433c9` |
| A | `backend/travel/tourism_serializers.py` | `5dd416579a38892232a18a7d99acb832523e7961a4b3b130532b7749de0c5cb7` |
| A | `backend/travel/tourism_service.py` | `df1ca95d6beb96c15e3a6d01442f1d4bde6fbd810a1ba5f5f7999c8566471d96` |
| A | `backend/travel/tourism_test_app.py` | `ef365a2bc3e03c53778966568ba5c70a5adca9ab7a1f4c65665cae72f2cc0746` |
| A | `backend/travel/tourism_test_settings.py` | `f2915198a561742b39f2351e76830ca98b6efcccaaaad352b554ca0f335870a8` |
| A | `backend/travel/tourism_test_urls.py` | `bbbb84af80a20464f8ec1942f65943ee53c7cad7c9b17f6721dae1520b45728f` |
| A | `backend/travel/tourism_tools.py` | `bc9440b1a529b0c4617cba5d79420bbfec52acff3947786d62100e5896d4d927` |
| A | `backend/travel/tourism_views.py` | `3159ffa4b72766901929b74875976f531fc80cb7533161367ae9e138e0b029b7` |
| M | `frontend/app/directions-api/route.ts` | `4ff6bfe6aeebe6524ffbfef5af5b62b30abbcbb6666bede98cfaa7a71fa0b015` |
| D | `frontend/app/tour-api/route.ts` | baseline `bac53b6ada2e1586d114d08dff54cc7f45b24e12634918226da6f2f6d39058a4` |
| M | `frontend/components/nearby-route-planner.tsx` | `2c33efd00ad4f23dd6dcef61cdebf4fe542b56d1dbc874e403ea16484af03c2b` |
| D | `frontend/lib/tour-api-server.ts` | baseline `431c3c026bd526905b9f8b22e615654cc10ea494248165babf11971717dbd484` |
| M | `frontend/lib/tour-api.ts` | `da61f3f49beae4ea714163513c99cc853e0034bedf09129c65b470e5af35887e` |
| M | `frontend/lib/tour-places.ts` | `16ffd7360a0afb19802392e97da232fc148a8b3c5876a4449e141a0e350e0245` |
| M | `frontend/tests/directions-api-route.test.mjs` | `96d989bce817af552dba0999a5722b17f593b600b4012a0554c22379661ba188` |
| M | `frontend/tests/tour-places.test.mjs` | `c481673e259c6748e1960f8413d83bb1f5f216b023c27b1a06b2aa6e7cfe0346` |

이 보고서 자체는 self-referential hash가 되므로 표에서 제외합니다.
