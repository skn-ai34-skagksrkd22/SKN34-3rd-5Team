# Python 환경 설정 (uv / VS Code)

기존 링크를 유지하기 위해 파일명은 그대로 두고, 설치 방식은 uv로 통일했습니다.
uv를 설치한 뒤 프로젝트 루트에서 실행합니다.

```bash
uv sync --project backend --locked
```

백엔드·크롤링·전처리 의존성은 `backend/pyproject.toml`, 정확한 버전은 `backend/uv.lock`에서 관리합니다.
가상환경은 `backend/.venv`에 생성되며 별도 활성화 없이 실행할 수 있습니다.

```bash
uv run --project backend --locked python crawling/kbo_standing.py
uv run --project backend --locked python crawling/kbo_schedule.py
uv run --project backend --locked python crawling/collect_kakao_places.py
uv run --project backend --locked python preprocessing/parse_ticket_policy.py
```

실행 시 `data/preprocessed/`의 결과 파일이 갱신됩니다.
카카오 수집에는 루트 `.env`의 `KAKAO_REST_API_KEY`가 필요합니다. 실제 키는 Git에 올리지 않습니다.

VS Code의 `Python: Select Interpreter`에서 Windows는 `backend/.venv/Scripts/python.exe`,
macOS/Linux는 `backend/.venv/bin/python`을 선택합니다. `.venv`는 커밋하지 않습니다.
