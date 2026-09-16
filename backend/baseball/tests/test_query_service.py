import os
from unittest.mock import Mock
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from baseball.limits import positive_int_env
from baseball.query_repository import BaseballQueryRepository
from baseball.query_service import BaseballQueryService, BaseballQueryValidationError


@override_settings(BASEBALL_QUERY_MAX_ROWS=200, BASEBALL_QUERY_MAX_SQL_BYTES=32768)
class BaseballQueryServiceTest(SimpleTestCase):
    def setUp(self):
        self.repository = Mock(spec=BaseballQueryRepository)
        self.repository.models.return_value = BaseballQueryRepository.models()
        self.repository.execute_readonly.return_value = {
            "columns": [],
            "rows": [],
            "truncated": False,
        }
        self.service = BaseballQueryService(self.repository)

    def test_all_19_models_and_foreign_keys_are_in_schema(self):
        schema = BaseballQueryRepository().get_schema()
        tables = {table["name"]: table for table in schema["tables"]}
        # 직관 도메인 19개 + 외부 제공자 통합(bef6de9)으로 늘어난 baseball_* 9개
        self.assertEqual(len(tables), 28)
        self.assertEqual(schema["schema"], "public")
        self.assertEqual(tables["GAME"]["quoted_name"], '"GAME"')
        game_columns = {column["name"]: column for column in tables["GAME"]["columns"]}
        self.assertEqual(
            game_columns["home_team_id"]["references"],
            {"table": "TEAM", "column": "id"},
        )

    def test_join_aggregate_subquery_and_readonly_cte_are_allowed(self):
        queries = (
            'SELECT h.team_name_ko, a.team_name_ko, s.stadium_name_ko FROM "GAME" g JOIN "TEAM" h ON h.id=g.home_team_id JOIN "TEAM" a ON a.id=g.away_team_id JOIN "STADIUM" s ON s.id=g.stadium_id',
            'SELECT t.team_name_ko, COUNT(*), AVG(g.home_score) FROM "TEAM" t JOIN "GAME" g ON g.home_team_id=t.id GROUP BY t.id',
            'SELECT * FROM "TEAM" WHERE id IN (SELECT home_team_id FROM "GAME")',
            'WITH recent AS (SELECT * FROM "GAME") SELECT * FROM recent r JOIN "TEAM" t ON t.id=r.home_team_id',
            'WITH "TEAM" AS (SELECT * FROM "GAME") SELECT * FROM "TEAM"',
        )
        for query in queries:
            with self.subTest(query=query):
                self.service.execute_baseball_select(query, {}, 20)
        self.assertEqual(self.repository.execute_readonly.call_count, len(queries))

    def test_boolean_conditions_and_case_are_allowed(self):
        queries = (
            'SELECT COUNT(*) FROM "GAME" g JOIN "TEAM" t ON t.id=g.home_team_id WHERE t.team_code = %(team)s AND g.game_date >= CURRENT_DATE',
            'SELECT * FROM "GAME" WHERE home_score > away_score OR home_score IS NULL',
            'SELECT CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_win FROM "GAME"',
        )
        for query in queries:
            with self.subTest(query=query):
                self.service.execute_baseball_select(query, {"team": "KIA"}, 20)
        self.assertEqual(self.repository.execute_readonly.call_count, len(queries))

    def test_named_parameter_is_not_interpolated(self):
        value = "1); DELETE FROM \"TEAM\"; --"
        self.service.execute_baseball_select(
            'SELECT * FROM "TEAM" WHERE team_name_ko = %(name)s', {"name": value}, 10
        )
        sql, params, max_rows = self.repository.execute_readonly.call_args.args
        self.assertIn("%(name)s", sql)
        self.assertEqual(params, {"name": value})
        self.assertEqual(max_rows, 10)

    def test_write_and_parser_bypasses_are_rejected(self):
        invalid = (
            'UPDATE "TEAM" SET team_name_ko=\'x\'',
            'SELECT * FROM "TEAM"; SELECT * FROM "GAME"',
            'WITH changed AS (DELETE FROM "GAME" RETURNING *) SELECT * FROM changed',
            'SELECT * INTO copied FROM "TEAM"',
            'SELECT * FROM "TEAM" FOR UPDATE',
            'SELECT * FROM auth_user',
            'SELECT * FROM llm_chatmessage',
            'SELECT * FROM pg_catalog.pg_roles',
            'SELECT 1',
            'SELECT * FROM ONLY "TEAM"',
            'SELECT * FROM TEAM',
            'WITH "TEAM" AS (SELECT * FROM auth_user) SELECT * FROM "TEAM"',
            'SELECT pg_sleep(1) FROM "TEAM"',
            'SELECT current_setting(\'data_directory\') FROM "TEAM"',
            'SELECT public.lower(team_name_ko) FROM "TEAM"',
            'SELECT CAST(team_name_ko AS public.evil) FROM "TEAM"',
            'SELECT team_name_ko OPERATOR(public.+) team_name_ko FROM "TEAM"',
            'SELECT team_name_ko::regclass FROM "TEAM"',
            'SELECT * FROM "TEAM" WHERE id = %s',
            'SELECT * FROM "TEAM" WHERE id = ?',
            'WITH RECURSIVE games AS (SELECT * FROM "GAME") SELECT * FROM games',
            'SELECT (WITH RECURSIVE games AS (SELECT * FROM "GAME") SELECT COUNT(*) FROM games) FROM "TEAM"',
        )
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(BaseballQueryValidationError):
                self.service.execute_baseball_select(query, {}, 10)
        self.repository.execute_readonly.assert_not_called()

    def test_limits_and_input_types_are_rejected(self):
        for max_rows in (0, 201, True):
            with self.subTest(max_rows=max_rows), self.assertRaises(BaseballQueryValidationError):
                self.service.execute_baseball_select('SELECT * FROM "TEAM"', {}, max_rows)
        with self.assertRaises(BaseballQueryValidationError):
            self.service.execute_baseball_select('SELECT * FROM "TEAM"', [], 10)
        with self.assertRaises(BaseballQueryValidationError):
            self.service.execute_baseball_select('SELECT \ud800 FROM "TEAM"', {}, 10)


class BaseballQueryLimitSettingsTest(SimpleTestCase):
    def test_limit_environment_must_be_a_positive_integer(self):
        for value in ("0", "-1", "invalid"):
            with self.subTest(value=value), patch.dict(os.environ, {"TEST_LIMIT": value}):
                with self.assertRaises(ImproperlyConfigured):
                    positive_int_env("TEST_LIMIT", 1)
        with patch.dict(os.environ, {"TEST_LIMIT": "25"}):
            self.assertEqual(positive_int_env("TEST_LIMIT", 1), 25)
