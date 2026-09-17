# TVING KBO relational 도구 인계

## canonical 모델과 재사용 결정

TVING과 CSV에 같은 논리 엔티티가 있으면 한 canonical 행만 유지하고 TVING을 우선합니다.

| 모델 | 결정 | 이유 |
| --- | --- | --- |
| `baseball.Team` | 재사용 | TVING 코드 10종을 기존 canonical 팀 코드로 명시 매핑 |
| `baseball.Game` | 재사용 | 날짜·원정·홈·시각으로 CSV 경기를 승격하고 TVING ID는 `source_external_code`에 보존 |
| `baseball.StandingHistory` | 재사용 | 팀+날짜 unique identity가 TVING 일일 순위와 동일 |
| `travel.Place` | 다른 provider와 공통 재사용 | 관광지·카카오 공통 장소 원장은 하나 |
| `TvingScheduleDay` | 신규 | 무경기와 미수집을 구분하는 날짜 단위 근거 |
| `TvingPlayer` | 신규 | 기존 저장소에 선수 master가 없음 |
| `TvingTeamProfile` | 신규 extension | 팀 이미지·배경·짧은 표시명만 보존하며 canonical 팀명은 중복하지 않음 |
| `TvingTeamSeasonRecord` | 신규 | 팀 상세의 제목/값 시즌 기록 |
| `TvingPlayerSeasonRecord`, `TvingPlayerCareerRecord` | 신규 | 선수별 순위 metric, 시즌 그래프, 통산 행 |
| `TvingTeamRoster`, `TvingTeamTopPlayer` | 신규 relation | 현재 선수단과 팀 내 TOP 기록 관계 |

`TvingTeamRoster`와 `TvingTeamTopPlayer`는 현재 provider 상태만 나타내며 시즌 history를 주장하지 않습니다. `TvingSnapshot`은 이전 구현 자료의 비파괴 backfill source로만 남고 refresh는 더 이상 snapshot에 쓰지 않습니다.

## TVING 우선과 CSV replay

`baseball.Team/Game/StandingHistory`의 `source` 기본값은 `csv`입니다. TVING이 확인한 행은 `source=tving`, `source_fetched_at`, `last_synced_at`으로 승격합니다.

- 먼저 전체 TVING batch의 정확한 CSV 경기 `(date, away, home, time)`를 예약합니다.
- 이미 다른 non-null TVING ID에 묶인 행은 후보에서 제외합니다.
- 예약된 exact match, 남은 단일 date+teams reschedule 후보, 신규 ID 순으로 처리합니다.
- date+teams 후보가 여러 개인데 exact match가 없으면 더블헤더 ambiguity로 전체 transaction을 거절합니다.
- 서로 다른 TVING 경기 ID는 같은 팀·날짜여도 절대 합치지 않습니다.
- 기존 CSV 행을 승격할 때 PK와 `game_code`는 유지합니다. 신규 TVING 경기의 stable PK가 점유됐으면 제한된 선형 probe로 빈 PK를 선택합니다.
- CSV loader replay는 `source=tving` Team/Game/Standing 행을 mutation 전에 통째로 skip합니다. field-wise fill이나 timestamp reset은 없습니다.
- provider 응답에서 사라진 행은 삭제하지 않습니다. `TvingScheduleDay.game_codes`가 현재 화면 projection만 구분합니다.

`baseball.0002` historical migration은 loader가 신규 source field를 feature-detect하므로 과거 app registry에서도 동작합니다. 원본 CSV는 수정하거나 삭제하지 않습니다.

## callable과 HTTP

```python
from tving.service import (
    refresh_daily, refresh_month, refresh_team, refresh_athlete,
    search_entities, create_player, update_player, delete_player,
    details_status,
)
```

- refresh: `refresh_daily("2026-09-15")`, `refresh_month("2026-09")`, `refresh_team("LG")`, `refresh_athlete("67119")`.
- DB-only search: `search_entities(kind="game|standing|team|player|roster|player-season|team-top", team=..., player=..., date=..., month=..., page=1, page_size=50)`.
- player CRUD는 authenticated+staff actor가 필요합니다. HTTP는 `/tving/entities/`, `/tving/entities/players/`, `/tving/entities/players/{code}/`입니다.
- legacy snapshot CRUD `/tving/snapshots/`는 backfill 자료 관리용이며 canonical 조회 도구가 아닙니다.

각 명시적 refresh는 공급자를 호출합니다. `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS` 기본 600초는 각 entity/domain의 DB 쓰기만 억제합니다. null 또는 strictly old만 쓰고, 정확한 경계·미래·fresh는 UPDATE와 timestamp sliding이 없습니다. roster/ranking에서 선수를 발견해도 `profile_last_synced_at`은 설정하지 않으며 identity와 profile 시각은 독립입니다.

반환 `providerFetchedAt`은 이번 공급자 조회 시각, `lastSyncedAt`은 화면을 구성한 canonical DB 행 중 가장 오래된 실제 동기화 시각입니다. 공급자 실패 시 완전한 ORM projection이 있을 때만 `stale:true`로 반환합니다.

## legacy backfill

```bash
python manage.py backfill_tving_snapshots
```

명령은 legacy snapshot을 삭제하지 않고 관계형 persister로 전달합니다. 유효한 행은 idempotent하게 승격하고 잘못되거나 매핑되지 않은 행은 보존한 채 `migrated`, `skipped`, `preserved` 수를 출력합니다. 실제 DB에서는 자동 실행하지 않습니다.

## 실제 검증 요약, 2026-09-15

전용 `tving-backend-test` PostgreSQL에서 최초 CSV 적재 후 actual TVING 일일 HTTP를 호출했습니다.

- 호출 전 `Game=782`, 당일 Game 4개 모두 `source=csv`.
- 호출 후 `Game=782` 그대로, 당일 4개가 같은 PK/game_code에서 `source=tving`으로 승격. 신규 중복 0.
- 실제 응답: 4경기, 10팀, 투수 18명, 타자 47명, `stale=false`.
- 600초 안의 두 번째 호출은 provider 시각만 변경되고 DB sync 시각은 동일.
- CSV 4,166 source rows replay 후 imported 0, TVING Game 4개 whole-row skip. 승격 전후 PK/game_code/source/timestamp manifest가 byte-for-byte 동일.
- 실제 월: 108경기, ready 26일, empty 4일. LG 상세: roster 20/14/10/5명, 투수·타자 각 7 group. 선수 67119: 시즌 8개, 통산 9행.
- LG Team 승격 뒤 CSV replay에서 `Team.tving_skipped=1`, 9월 전체 승격 후 `Game.tving_skipped=108`.

테스트 명령과 전체 통합 결과는 `docs/handoffs/PROVIDER_INTEGRATION_REPORT.md`에 있습니다. LLM 등록·prompt·RAG 변경과 autonomous 전체 선수 backfill은 범위 밖입니다.
