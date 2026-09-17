# 야구 읽기 전용 SQL 조회 서비스

`BaseballQueryService`는 `baseball` 앱의 현재 모델 19개를 스키마 정보로 제공하고, 이 테이블만 사용하는 단일 PostgreSQL SELECT를 실행합니다.

## DB 준비

1. 운영 DB에 이미 대문자 야구 테이블이 있다면 `backend/baseball/migrations/0001_initial.py`와 실제 구조 및 migration 이력을 먼저 비교합니다. 확인 없이 `--fake`, DROP 또는 재생성을 하지 않습니다.
2. 기본 DB 소유자와 다른 `BASEBALL_DB_USER`, `BASEBALL_DB_PASSWORD`를 설정합니다. 실제 비밀번호는 `.env.example`이 아닌 비밀 저장소나 배포 환경에 둡니다.
3. 전용 DB에서 PostgreSQL 기본 `PUBLIC TEMPORARY`만 정리하려면 `--prepare-db-permissions`를 사용합니다. 이 옵션은 현재 DB에 한해 기본 DB 사용자에게 `TEMPORARY`를 명시적으로 부여한 뒤 `PUBLIC`에서만 회수합니다. 다른 역할의 명시적 권한과 `PUBLIC CREATE`/`CONNECT`, schema 권한은 바꾸지 않습니다.
4. 이 변경은 같은 DB를 사용하는 다른 역할이 `PUBLIC`을 통해 임시 테이블을 만들던 동작을 막습니다. 영향 범위를 확인한 운영자가 DB `GRANT`/`REVOKE` 권한과 역할 생성·변경 및 schema/table 권한을 가진 기본 연결로 실행해야 합니다.

```sql
-- 나머지 위험 권한은 영향 검토 후 DBA가 별도로 적용
REVOKE CREATE ON DATABASE your_database FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
```

```bash
cd backend
python manage.py migrate
python manage.py provision_baseball_reader --prepare-db-permissions
```

옵션을 생략하면 기존 fail-closed 동작을 유지해 `PUBLIC`의 DB `CREATE`/`TEMPORARY`를 자동 변경하지 않고 실패합니다. 옵션의 두 권한 변경과 기존 감사·역할 생성·grant는 한 트랜잭션이므로 후속 감사나 설정이 실패하면 모두 롤백되며, 반복 실행해도 같은 상태를 유지합니다. 명령은 대상 역할의 superuser·createdb·createrole·replication·bypassrls·inherit, role 멤버십, 객체 소유 여부를 확인합니다. 현재 ACL뿐 아니라 `pg_default_acl`의 명시적 table·sequence·schema·function grant도 검사하며, 그 밖의 `PUBLIC` 또는 reader 위험 정책은 자동 변경하지 않고 실패합니다.

`BASEBALL_DB_USER`와 `BASEBALL_DB_PASSWORD`는 계속 배포 환경이나 비밀 저장소에 보관합니다. 이 절차와 테스트는 운영 DB를 직접 수정하지 않으며, 운영 적용은 반드시 대상이 전용 DB인지 확인한 뒤 별도로 수행합니다.

## Python 사용

```python
from baseball.query_service import BaseballQueryService

service = BaseballQueryService()
schema = service.get_baseball_schema()
result = service.execute_baseball_select(
    'SELECT t.team_name_ko, COUNT(*) AS games '
    'FROM "TEAM" t JOIN "GAME" g ON g.home_team_id = t.id '
    'WHERE g.game_date >= %(start)s GROUP BY t.id, t.team_name_ko',
    {"start": "2026-01-01"},
    max_rows=100,
)
```

테이블명은 모델의 실제 대문자 이름처럼 반드시 인용합니다. 값은 psycopg named placeholder로만 전달합니다. literal `%`가 있는 LIKE, `%` 나머지 연산, literal `%(text)s`와 실제 named parameter의 혼합도 지원합니다. JOIN·집계·서브쿼리·비재귀 읽기 전용 CTE는 지원하지만 쓰기/DDL/COPY, 다중 문장, 잠금 SELECT, `SELECT INTO`, `FROM ONLY`, 다른 스키마·테이블, 재귀 CTE 및 허용 목록 밖 함수는 거부합니다.

반환값은 `columns`, `rows`, `truncated`입니다. 날짜·시간은 ISO 8601 문자열, `Decimal`은 문자열, NULL은 `None`이며 중복 컬럼명을 보존하기 위해 행은 배열입니다. 기본 제한은 200행, SQL 32 KiB, 응답 1 MiB, 실행 3초, 잠금 대기 1초이고 환경변수로 더 엄격하게 운영할 수 있습니다.

## 오류와 점검

- `BaseballQueryValidationError`: SQL·파라미터·행 제한 정책 위반
- `BaseballQueryConfigurationError`: 전용 자격증명 누락
- `BaseballQueryAccessDeniedError`: PostgreSQL 권한 거부
- `BaseballQueryTimeoutError`: 실행시간 초과
- `BaseballQueryLockTimeoutError`: 잠금 대기시간 초과
- `BaseballQueryResultTooLargeError`: 단일 행이 응답 제한 초과
- `BaseballQueryExecutionError`: 그 밖의 DB 실행 실패(원시 DB 오류는 외부에 노출하지 않음)

운영 적용 전에는 전용 역할로 19개 테이블 SELECT가 되고 accounts/llm 조회와 모든 쓰기가 거부되는지 직접 확인합니다. migration, table/sequence 추가, 함수 배포 또는 권한 변경 뒤에는 `provision_baseball_reader`를 다시 실행해 현재 ACL과 default ACL을 재감사해야 합니다. 이 명령은 실행 시점의 상태를 검사할 뿐 이후 DBA가 추가하는 임의 grant를 영구 차단하지 않으며, 서비스 검증의 최종 보안 경계는 별도 PostgreSQL 역할과 읽기 전용 트랜잭션입니다.

## 안전한 테스트

단위 테스트는 DB를 만들거나 연결하지 않고, project `.env`를 읽지 않는 고정 설정을 사용합니다.

```bash
cd backend && uv run --python 3.13.5 --isolated --with-requirements requirements.txt python manage.py test baseball.tests.test_query_service baseball.tests.test_query_repository --settings=baseball.tests.unit_settings -v 2
```

PostgreSQL 통합 검사는 저장소 루트에서 아래 한 명령으로 실행합니다.

```bash
python3 backend/baseball/tests/run_postgres_integration.py
```

runner는 UUID 기반 이름, 별도 owner/reader 암호, Docker가 배정한 임의의 loopback port를 사용합니다. 전용 test settings는 project settings나 dotenv를 import하지 않고 소유 container token과 격리 DB/role 규칙을 확인한 뒤에만 migration·fixture·grant를 허용합니다. 성공·실패와 무관하게 label과 container ID가 모두 일치하는 이번 실행의 container만 제거하며, integration test는 skip으로 성공 처리되지 않습니다.

## LangChain 도구

`llm.tools`는 기존 서비스를 그대로 호출하는 도구 두 개를 제공합니다.

1. `get_baseball_schema`: 먼저 호출해 `public` 스키마의 허용 테이블, 대문자 quoted name, 컬럼, FK 관계를 확인합니다.
2. `execute_baseball_select`: 스키마 결과로 작성한 PostgreSQL 단일 `SELECT`를 실행합니다. JOIN, 집계, 서브쿼리, 비재귀 CTE와 `%(name)s` named parameter를 지원하며 `max_rows`로 결과를 제한합니다.

```python
from llm.tools import execute_baseball_select, get_baseball_schema

schema = get_baseball_schema.invoke({})
result = execute_baseball_select.invoke({
    "sql": 'SELECT t.team_name_ko, COUNT(g.id) FROM "TEAM" t JOIN "GAME" g ON g.home_team_id=t.id GROUP BY t.id',
    "params": {},
    "max_rows": 100,
})
```

도구는 SQL을 생성하지 않고, 기본 DB로 우회하지 않으며, 서비스 검증과 제한을 중복 없이 사용합니다. 예상된 입력·조회 오류는 안전한 메시지로 반환하고 예상하지 못한 오류는 전파합니다. LangChain의 `.invoke()`와 `.ainvoke()`에서 사용할 수 있으며 ChatService는 제한된 도구 계획 뒤 도구가 비활성화된 최종 답변을 스트리밍합니다. RAG 흐름에는 연결하지 않습니다.
