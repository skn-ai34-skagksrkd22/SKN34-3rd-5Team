# 야구 CSV 데이터 마이그레이션

`baseball.0002_load_baseball_csv_data`는 최초 `migrate` 때 저장소의 `data/` CSV를 19개 야구 모델에 한 번 적재한다. 기존 PK 행과 natural key 행은 수정하지 않으며, stable ID 충돌·필수 파일 누락·잘못된 값은 전체 트랜잭션을 실패시켜 migration 기록을 남기지 않는다. reverse는 이미 운영 데이터가 될 수 있는 행을 삭제하지 않는 명시적 noop이다.

저장소 실행에서는 `<repo>/data`, Compose backend에서는 read-only mount `/data`를 읽는다. 두 Compose 파일 모두 이미 전체 `data` 디렉터리를 `/data:ro`로 마운트하므로 설정 변경은 없다. 필수 파일이 없으면 누락된 실제 경로와 함께 실패하며 조용히 건너뛰지 않는다.

## 적재 보고서

2026-09-15 `csv.DictReader` 독립 행 수와 CLI dry-run 결과다. 오류/거부 행은 0건이며, 전체 source 4,166행 중 지원 CSV에서 3,125개 모델 행을 생성한다. source 행과 destination 행은 1:N 분해 및 미지원 파일 때문에 같지 않다.

| 지원 source | CSV 행 |
| --- | ---: |
| `raw/team_stadium_code_map.csv` | 10 |
| `preprocessed/구장운영정보.csv` | 9 |
| `preprocessed/stadium_coordinates.csv` | 9 |
| `preprocessed/kbo_schedule_postseason_tbd.csv` | 4 |
| `preprocessed/kbo_schedule_full.csv` | 782 |
| `preprocessed/kbo_standing_history.csv` | 10 |
| `preprocessed/구장좌석구역.csv` | 192 |
| `preprocessed/구장티켓가격.csv` | 740 |
| `preprocessed/kbo_ticket_policy_structured.csv` | 244 |
| `preprocessed/구장좌석도.csv` | 10 |
| `preprocessed/구장좌석경험.csv` | 8 |
| `preprocessed/구장교통정보.csv` | 43 |
| `preprocessed/구장먹거리_공식매점.csv` | 291 |
| `preprocessed/구장부가콘텐츠_공식.csv` | 68 |
| `preprocessed/구장편의시설.csv` | 207 |

| destination 모델 | 생성 행 |
| --- | ---: |
| Team | 10 |
| Stadium | 9 |
| HomeContext | 10 |
| PostseasonStage | 4 |
| Game | 782 |
| StandingHistory | 10 |
| SeatZone | 192 |
| TicketPrice | 740 |
| TicketPolicy | 244 |
| SeatMap | 10 |
| SeatMapAsset | 14 |
| SeatScope | 8 |
| SeatView | 8 |
| Transport | 43 |
| FoodStore | 291 |
| FoodStoreLocation | 291 |
| FoodStoreMenu | 184 |
| StadiumContent | 68 |
| Facility | 207 |

명시적 미적재 source는 `kbo_standing.csv` 10행(필드가 부족한 최신 요약), `external_places.csv` 1,008행(대응 모델 없음), `3차_신규확보데이터.csv` 14행(새 스키마 보류), `구장먹거리_위치_자리어때.csv` 385행과 `구장편의시설_위치_자리어때.csv` 100행(비공식), `구장편의시설_보류이력.csv` 8행, `구장잔여정보_좌석주차버스.csv` 14행이다. README에 보이는 raw `kbo_schedule.csv`, raw `kbo_ticket_policy.csv`도 전처리 결과와 겹치므로 직접 적재하지 않는다. “모든 CSV 적재”를 약속하지 않고 이 목록을 유지한다.

## 이후 CSV 갱신

Migration의 버전 고정 대상은 배포 시점 checkout에 포함된 CSV 스냅샷과 그 매핑 코드다. 이미 적용된 migration은 이후 CSV 편집을 다시 가져오지 않지만, 아직 적용하지 않은 새 checkout은 그 checkout의 갱신된 CSV를 읽을 수 있다. 배포 후 새 CSV 행을 반영할 때는 migration을 재실행하지 말고 기존 CLI를 사용한다.

```bash
cd backend
python manage.py import_baseball_data --dry-run --report /tmp/baseball-import.json
python manage.py import_baseball_data --report /tmp/baseball-import.json
```

CLI는 기존과 같이 additive/idempotent이며 natural key가 이미 있는 행을 갱신하지 않고 새 행만 추가한다. dry-run·JSON report 동작을 유지하므로 실제 반영 전 보고서의 `rejected`, `rolled_back`, source/destination counts를 확인한다.

## 검증 명령

```bash
uv run --isolated --with-requirements backend/requirements.txt python backend/manage.py test baseball.tests.test_import --settings=baseball.tests.import_settings -v 1
uv run --isolated --with-requirements backend/requirements.txt python backend/manage.py test baseball.tests.test_csv_migration --settings=baseball.tests.migration_settings -v 1
uv run --isolated --with-requirements backend/requirements.txt python backend/baseball/tests/run_postgres_integration.py
docker compose -f docker/community.compose.yml config --quiet
```
