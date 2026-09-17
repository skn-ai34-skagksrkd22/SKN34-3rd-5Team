# 외부 provider 통합 검증 보고서

기준 HEAD는 `707699f`, 작업 branch는 사용자 승인 예외인 `Seongho-haru/feat-tving`입니다. 커밋·push·merge·deploy와 실제 `.env`·live DB 변경은 하지 않았습니다.

## 통합 출처와 복구 근거

통합 직전 부모 변경 전체를 파일별 SHA-256으로 출력해 터미널 기록에 남겼습니다. 주요 부모 보존 hash는 `backend/tving/service.py=4d09e803...`, `frontend/components/game-schedule.tsx=5cf06671...`, `backend/config/settings.py=25b628b3...`였습니다.

- KMA 인계: `docs/handoffs/WEATHER_TOOL_HANDOFF.md` source SHA `329cd2cb...`; 10개 비공유 파일은 source와 SHA 일치, `game-schedule.tsx`는 TVING URL을 보존하고 source label 한 줄만 결합.
- Routing 인계: `docs/handoffs/EXTERNAL_TRAVEL_TOOLS_HANDOFF.md`; 17개 non-shared 파일을 manifest와 대조해 복사하고 URL/settings/Compose는 수동 합성.
- Tour 인계: `docs/handoffs/TOURISM_TOOLS_HANDOFF.md` SHA `9d281652...`; Place-backed 최종 파일만 복사. 이전 중복 관광 master draft는 통합하지 않음.
- Place 재사용: local `develop ae09080`의 `0006_place.py` SHA `65fc787f...`와 service/serializer/view/tests를 사용. `Place.phone` model은 transition migration에 맞춰 120, 기존 Kakao HTTP serializer는 50 유지.

## 최종 데이터 소유권

- TVING: 기존 `baseball.Team`, `Game`, `StandingHistory`를 canonical로 재사용. 선수와 TVING 고유 profile/record/relation만 `tving` 모델로 추가.
- Kakao 장소와 Tour: `travel.Place` 한 원장을 공유. `TourismPlace`는 content ID/type/category/image와 관광 freshness만 가진 OneToOne extension.
- Directions: 사용자 저장 Course와 의미가 다른 provider route identity라 `DirectionsRoute` 신규 모델을 유지.
- Weather: live-only callable/API. 모델·migration·600초 cache·DB fallback 없음.
- legacy `TvingSnapshot`/`ExternalProviderSnapshot`: backfill source만 유지하고 신규 canonical refresh는 쓰지 않음.

## 환경과 endpoint

전용 Compose project `tving-backend-test`만 사용했습니다.

| service | host port | 상태 |
| --- | --- | --- |
| PostgreSQL 18/pgvector | `127.0.0.1:18074` | healthy, disposable |
| Django 6.1.1/Python 3.12.14 | `127.0.0.1:18874` | running |
| Next 16.3.4/Node 22.22.0 | `127.0.0.1:18078` | running |
| Nginx | `127.0.0.1:18079` | running |

Nginx 실제 경로 결과:

- `/` 200, `/api/tving/daily/` 200.
- `/api/weather/`은 의도적으로 key 없는 환경에서 sanitized 503.
- `/api/tourism/`은 key 없는 환경에서 truthful 200 `unconfigured`.
- 제거된 `/kbo-api`, `/weather-api`, `/tour-api`, `/directions-api`는 모두 404.
- gstack headless browser binary는 이 머신에 build되지 않아 skill browser 실행은 중단했습니다. 대신 disposable Next+Nginx+Django 전체 HTTP hop을 직접 검증했으며 기존 80/3000/8000 컨테이너는 건드리지 않았습니다.

## 자동 검증

최종 단일 명령:

```bash
./docker/run-provider-acceptance.sh
```

결과:

- Django 통합: 118/118 (`tving.tests`, `travel.tests`, directions, tourism, weather, places, community predictions).
- Baseball CSV importer isolated settings: 6/6.
- Baseball API isolated settings: 15 pass, 환경 의존 2 skip, 실패 0.
- Frontend 전체: 251 pass, 기존 skip 1, 실패 0.
- ESLint: 오류 0, 범위 밖 기존 `community-post-bottom.tsx` `<img>` warning 1.
- Next production build: 성공, route manifest에 provider Next relay 없음.
- `makemigrations --check --dry-run`: `No changes detected`.
- `spectacular --validate --fail-on-warn`: warning/error 0.
- 생성 OpenAPI와 `contracts/openapi.yaml`, openapi-typescript 결과와 `frontend/lib/api/schema.d.ts`를 각각 byte compare: 일치.

## 실제 provider와 DB 증거

TVING은 fixture가 아닌 public provider를 Django HTTP로 호출했습니다.

- 호출 전 CSV `Game=782`, 2026-09-15 4개 모두 `source=csv`.
- 호출 후 전체 `Game=782`, 같은 4개 PK/game_code가 `source=tving`과 TVING external ID로 승격. 응답은 4경기·10팀·투수18·타자47, stale false.
- 600초 내 재호출은 provider timestamp만 변경되고 DB sync timestamp는 동일.
- CSV 4,166 source rows replay 후 imported 0. 승격 Game/Standing/Team provenance와 timestamp manifest는 replay 전후 byte-identical.
- 실제 9월 월별 108경기, ready 26/empty 4; LG roster 20/14/10/5와 순위 group 7/7; 선수 67119 시즌8/통산9.

KMA live 성공(21°C/맑음)과 Directions car/walk/transit 실제 성공은 각 독립 worker/coordinator가 key를 메모리로만 넣어 검증한 결과이며 이 통합 run에서는 secret을 다시 읽지 않았습니다. Tour live는 provider가 `upstream_unavailable`로 거절했으므로 성공을 주장하지 않습니다. mock provider+실제 PostgreSQL 관계/rollback/freshness 검증은 통과했습니다.

## 설정 소유권과 cleanup

`KMA_SERVICE_KEY`, `KMA_API_KEY`, `KAKAO_REST_API_KEY`, `TOUR_API_KEY`는 Compose backend에만 전달합니다. `NEXT_PUBLIC_KAKAO_MAP_KEY`만 browser 공개이고, frontend env에는 server key가 없습니다. `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS=600`은 TVING, Directions, Place, Tourism이 공유하며 Weather에는 적용하지 않습니다.

현재 환경은 코디네이터 확인을 위해 유지합니다. 이 작업이 소유한 환경만 제거하는 명령은 다음과 같습니다.

```bash
docker compose -p tving-backend-test -f docker/tving-backend-test.compose.yml down -v
```
