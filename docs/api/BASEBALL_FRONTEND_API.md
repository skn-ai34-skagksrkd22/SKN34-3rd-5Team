# 야구 CRUD·공개 API

Nginx 외부 경로는 `/api/baseball/`, Django 내부 경로는 `/baseball/`이다. 공개 GET은 익명 허용, `/manage/`의 GET/POST/PATCH/DELETE는 JWT로 인증된 활성 `is_staff`만 허용한다. ID는 19개 모델의 기존 `IntegerField(primary_key=True)`를 유지해 생성 시 명시하며 `MAX(id)+1`은 사용하지 않는다.

관리 자원은 `teams`, `stadiums`, `home-contexts`, `postseason-stages`, `games`, `standing-histories`, `seat-zones`, `ticket-prices`, `ticket-policies`, `seat-maps`, `seat-map-assets`, `seat-scopes`, `seat-views`, `food-stores`, `food-store-locations`, `food-store-menus`, `transports`, `stadium-contents`, `facilities` 19개다. 목록은 `{count,next,previous,results}`이고 기본 30·최대 100행이다. PUT과 bulk write는 지원하지 않는다. PATCH/DELETE는 상세 GET의 body snapshot(응답의 `_etag` 자체는 제외)에 대한 `_etag` 값을 `If-Match` 또는 body `_etag`로 보내며, stale write는 412, PROTECT 삭제는 409다.

공개 경로는 `teams/`, `stadiums/`, `stadiums/{code}/`, 구장 하위 `seat-zones|ticket-prices|seat-maps|seat-scopes|seat-views|food-stores|transports|facilities|contents/`, 그리고 `games/`, `standings/`, `postseason-stages/`, `ticket-prices/`, `ticket-policies/`다. 경기 기간은 최대 366일이고, 순위 날짜 생략 시 DB 전체의 최신 공통 snapshot 날짜를 사용한다. 구장 목록·상세는 DB 실패 때 정적 목록으로 대체하지 않으며 사진·지역·색상만 `stadium_code` 기반 presentation metadata를 덧붙인다.

정수 조회 필터는 모델 PK 범위의 양의 10진 정수, 날짜 필터는 정확한 `YYYY-MM-DD`만 받으며 잘못된 값은 400이다. 좌석도·asset URL은 호스트가 있는 유효한 `http` 또는 `https` URL만 저장하고 백엔드는 해당 URL을 요청하지 않는다.

초기 적재는 저장소 루트에서 다음처럼 실행한다. 실제 개발/공유 DB가 아닌 대상인지 먼저 확인한다.

```bash
cd backend
python manage.py import_baseball_data --dry-run --report ../.hermes/reports/baseball-import-dry-run.json
python manage.py import_baseball_data --report ../.hermes/reports/baseball-import.json
```

명령은 `data/raw/team_stadium_code_map.csv`와 대응되는 `data/preprocessed` CSV를 부모부터 transaction 안에서 신규 행만 적재한다. 자연키를 먼저 확인하고 BLAKE2s 기반 결정적 정수 PK 충돌은 전체 실패시킨다. 기존 자연키 행은 관리자 수정값을 덮어쓰지 않고 건너뛰며 absent row 삭제도 하지 않는다. 포스트시즌 TBD는 실제 Game이 아닌 PostseasonStage로만, 단일 `kbo_standing.csv`는 이력 아닌 최신 요약이라 미적재하고 `kbo_standing_history.csv`만 사용한다. 모델 밖 선수·외부 장소·비공식 자리어때 보강 필드는 report의 unsupported/provenance로 남긴다.
