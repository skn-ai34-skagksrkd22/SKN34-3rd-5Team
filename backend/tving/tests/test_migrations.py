from datetime import datetime, timezone

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CanonicalStateMigrationTests(TransactionTestCase):
    reset_sequences = True

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_populated_provider_tables_keep_rows_primary_keys_and_foreign_keys(self):
        executor = MigrationExecutor(connection)
        before = [("baseball", "0003_game_away_starting_pitcher_and_more"), ("tving", "0003_tvingplayer_career_positions_and_more")]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        Team = old.get_model("baseball", "Team")
        Player = old.get_model("tving", "TvingPlayer")
        Record = old.get_model("tving", "TvingPlayerSeasonRecord")
        Career = old.get_model("tving", "TvingPlayerCareerRecord")
        Profile = old.get_model("tving", "TvingTeamProfile")
        Roster = old.get_model("tving", "TvingTeamRoster")
        TeamRecord = old.get_model("tving", "TvingTeamSeasonRecord")
        TopPlayer = old.get_model("tving", "TvingTeamTopPlayer")
        Schedule = old.get_model("tving", "TvingScheduleDay")
        Snapshot = old.get_model("tving", "TvingSnapshot")
        now = datetime(2026, 9, 16, tzinfo=timezone.utc)
        team = Team.objects.create(id=1_999_999_901, team_code="MIG", team_name_ko="migration")
        player = Player.objects.create(external_code="999901", team=team, name="migration player")
        record = Record.objects.create(
            player=player, season=2026, record_kind="pitcher", record_key="ranking",
            rank=1, source_fetched_at=now,
        )
        career = Career.objects.create(player=player, position=0, season_label="2026", title="career", source_fetched_at=now)
        profile = Profile.objects.create(team=team, external_code="MG", short_name="migration", season_title="2026", source_fetched_at=now)
        roster = Roster.objects.create(team=team, player=player, position="pitcher", source_fetched_at=now)
        team_record = TeamRecord.objects.create(team=team, season=2026, category="main", title="wins", value="1", source_fetched_at=now)
        top = TopPlayer.objects.create(team=team, player=player, athlete_type="pitcher", category="era", rank=1, source_fetched_at=now)
        schedule = Schedule.objects.create(date="2026-09-16", status="empty", game_count=0, source_fetched_at=now)
        snapshot = Snapshot.objects.create(resource_kind="daily", resource_key="2026-09-16", payload={"date": "2026-09-16"}, source_fetched_at=now)

        after = [("baseball", "0006_alter_player_table_alter_playercareerrecord_table_and_more"), ("tving", "0005_delete_tvingscheduleday_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        current = executor.loader.project_state(after).apps
        Player = current.get_model("baseball", "Player")
        Record = current.get_model("baseball", "PlayerSeasonRecord")
        Career = current.get_model("baseball", "PlayerCareerRecord")
        Profile = current.get_model("baseball", "TeamProfile")
        Roster = current.get_model("baseball", "TeamRoster")
        TeamRecord = current.get_model("baseball", "TeamSeasonRecord")
        TopPlayer = current.get_model("baseball", "TeamTopPlayer")
        Schedule = current.get_model("baseball", "ScheduleDay")
        Snapshot = current.get_model("baseball", "ProviderSnapshot")
        moved_player = Player.objects.get(pk=player.pk)
        moved_record = Record.objects.get(pk=record.pk)
        self.assertEqual((Player.objects.count(), Record.objects.count()), (1, 1))
        self.assertEqual((moved_player.pk, moved_player.team_id, moved_record.pk, moved_record.player_id), (player.pk, team.pk, record.pk, player.pk))
        self.assertEqual(
            (Career.objects.get().pk, Profile.objects.get().pk, Roster.objects.get().pk, TeamRecord.objects.get().pk, TopPlayer.objects.get().pk),
            (career.pk, profile.pk, roster.pk, team_record.pk, top.pk),
        )
        self.assertTrue(all(model.objects.count() == 1 for model in (Career, Profile, Roster, TeamRecord, TopPlayer)))
        self.assertEqual(
            (
                Career.objects.get().player_id,
                Profile.objects.get().team_id,
                Roster.objects.get().team_id,
                Roster.objects.get().player_id,
                TeamRecord.objects.get().team_id,
                TopPlayer.objects.get().team_id,
                TopPlayer.objects.get().player_id,
            ),
            (player.pk, team.pk, team.pk, player.pk, team.pk, team.pk, player.pk),
        )
        self.assertEqual((Schedule.objects.get().pk, Snapshot.objects.get().pk), (schedule.pk, snapshot.pk))
        expected_tables = {
            "baseball_player",
            "baseball_playercareerrecord",
            "baseball_playerseasonrecord",
            "baseball_providersnapshot",
            "baseball_scheduleday",
            "baseball_teamprofile",
            "baseball_teamroster",
            "baseball_teamseasonrecord",
            "baseball_teamtopplayer",
        }
        self.assertEqual(
            {model._meta.db_table for model in (Player, Career, Record, Snapshot, Schedule, Profile, Roster, TeamRecord, TopPlayer)},
            expected_tables,
        )
        physical_tables = set(connection.introspection.table_names())
        self.assertTrue(expected_tables <= physical_tables)
        self.assertTrue(
            physical_tables.isdisjoint(
                {
                    "tving_tvingplayer",
                    "tving_tvingplayercareerrecord",
                    "tving_tvingplayerseasonrecord",
                    "tving_tvingsnapshot",
                    "tving_tvingscheduleday",
                    "tving_tvingteamprofile",
                    "tving_tvingteamroster",
                    "tving_tvingteamseasonrecord",
                    "tving_tvingteamtopplayer",
                }
            )
        )
