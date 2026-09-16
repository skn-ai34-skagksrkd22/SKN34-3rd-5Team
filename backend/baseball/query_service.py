import re

from django.conf import settings
from sqlglot import exp, parse
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import traverse_scope

from .query_repository import BaseballQueryRepository


class BaseballQueryValidationError(ValueError):
    pass


class BaseballQueryService:
    SAFE_FUNCTIONS = {
        "ABS",
        "AVG",
        "CASE",
        "CAST",
        "CEIL",
        "COALESCE",
        "CONCAT",
        "COUNT",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "EXTRACT",
        "FLOOR",
        "GREATEST",
        "LEAST",
        "LENGTH",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "ROUND",
        "SUBSTRING",
        "SUM",
        "TIMESTAMP_TRUNC",
        "TRIM",
        "UPPER",
    }

    def __init__(self, repository=None):
        self.repository = repository or BaseballQueryRepository()

    def get_baseball_schema(self) -> dict:
        return self.repository.get_schema()

    def execute_baseball_select(
        self, sql: str, params: dict | None = None, max_rows: int = 100
    ) -> dict:
        validated_sql = self._validated_sql(sql)
        params = {} if params is None else params
        if not isinstance(params, dict):
            raise BaseballQueryValidationError("params는 dict여야 합니다.")
        if (
            not isinstance(max_rows, int)
            or isinstance(max_rows, bool)
            or not 1 <= max_rows <= settings.BASEBALL_QUERY_MAX_ROWS
        ):
            raise BaseballQueryValidationError(
                f"max_rows는 1~{settings.BASEBALL_QUERY_MAX_ROWS} 사이여야 합니다."
            )
        return self.repository.execute_readonly(validated_sql, params, max_rows)

    def _validate_select_query(self, sql: str) -> None:
        self._validated_sql(sql)

    def _validated_sql(self, sql: str) -> str:
        if not isinstance(sql, str) or not sql.strip():
            raise BaseballQueryValidationError("SQL을 입력해야 합니다.")
        try:
            sql_size = len(sql.encode())
        except UnicodeError:
            raise BaseballQueryValidationError("SQL 문자열 인코딩이 올바르지 않습니다.") from None
        if sql_size > settings.BASEBALL_QUERY_MAX_SQL_BYTES:
            raise BaseballQueryValidationError("SQL 길이 제한을 초과했습니다.")
        try:
            statements = parse(sql, read="postgres")
        except (SqlglotError, ValueError, TypeError):
            raise BaseballQueryValidationError("PostgreSQL SELECT 문법이 올바르지 않습니다.") from None
        if len(statements) != 1 or not isinstance(statements[0], exp.Query):
            raise BaseballQueryValidationError("단일 SELECT 문만 허용됩니다.")

        statement = statements[0]
        forbidden = (exp.DDL, exp.DML, exp.Command, exp.Into, exp.Lock)
        if any(statement.find(kind) for kind in forbidden):
            raise BaseballQueryValidationError("읽기 전용 SELECT만 허용됩니다.")
        if any(with_clause.args.get("recursive") for with_clause in statement.find_all(exp.With)):
            raise BaseballQueryValidationError("재귀 CTE는 허용되지 않습니다.")
        if statement.find(exp.Operator):
            raise BaseballQueryValidationError("명시적 PostgreSQL 연산자는 허용되지 않습니다.")
        for data_type in statement.find_all(exp.DataType):
            if data_type.this == exp.DataType.Type.USERDEFINED:
                raise BaseballQueryValidationError("사용자 정의 타입 변환은 허용되지 않습니다.")
        if statement.find(exp.ObjectIdentifier):
            raise BaseballQueryValidationError("객체 식별자 타입 변환은 허용되지 않습니다.")
        for placeholder in statement.find_all(exp.Placeholder):
            if not isinstance(placeholder.this, exp.Identifier) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", placeholder.this.name
            ):
                raise BaseballQueryValidationError("named SQL parameter만 허용됩니다.")

        allowed_tables = {model._meta.db_table for model in self.repository.models()}
        base_tables = []
        for scope in traverse_scope(statement):
            for source in scope.sources.values():
                if not isinstance(source, exp.Table):
                    continue
                if source.args.get("only"):
                    raise BaseballQueryValidationError("FROM ONLY는 허용되지 않습니다.")
                if source.catalog or (source.db and source.db != "public"):
                    raise BaseballQueryValidationError("public 야구 테이블만 허용됩니다.")
                identifier = source.this
                if source.name not in allowed_tables or not identifier.args.get("quoted"):
                    raise BaseballQueryValidationError(
                        f"허용되지 않은 테이블입니다: {source.name}"
                    )
                base_tables.append(source.name)
        if not base_tables:
            raise BaseballQueryValidationError("야구 테이블을 조회하는 SELECT만 허용됩니다.")

        for function in statement.find_all(exp.Func):
            # sqlglot 28 에서는 AND·OR·XOR(Connector)도 Func 하위 클래스라 함수로 잡힌다.
            # 함수 호출이 아니라 조건 결합이므로 검사 대상에서 뺀다 (안 빼면 WHERE a AND b 가 전부 거부됨).
            if isinstance(function, exp.Connector):
                continue
            # CASE WHEN … THEN … 의 WHEN 가지도 sqlglot 에서는 If 노드다 (CASE 안에 있을 때만 허용)
            if isinstance(function, exp.If) and isinstance(function.parent, exp.Case):
                continue
            if isinstance(function.parent, exp.Dot):
                raise BaseballQueryValidationError("스키마 지정 함수는 허용되지 않습니다.")
            if isinstance(function, exp.Anonymous):
                name = function.name.upper()
            else:
                name = function.sql_name().upper()
            if name not in self.SAFE_FUNCTIONS:
                raise BaseballQueryValidationError(f"허용되지 않은 함수입니다: {name}")
        return statement.sql(dialect="postgres")
