"""Run without private bot resources: pytest --confcutdir=tests/unit tests/unit."""

import asyncio
from datetime import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time

from intfar.api.config import Config
from intfar.api.stat_period import StatPeriod, STATS_TIMEZONE


ROOT = Path(__file__).resolve().parents[2]


def _import_config(self):
    # Module discovery needs paths, but these tests never need API credentials.
    self.project_root = str(ROOT)
    self.startup_folder = str(ROOT / "src")
    self.src_folder = str(ROOT / "src/intfar")
    self.resources_folder = str(ROOT / "resources")


with patch.object(Config, "__init__", _import_config):
    from intfar.api.game_databases.lol import LoLGameDatabase
    from intfar.api.game_databases.cs2 import CS2GameDatabase
    from intfar.discbot.commands.base import get_handler, StatCommand
    from intfar.discbot.commands import util as command_util
    from intfar.discbot.commands.stats import (
        AverageCommand, BestStatCommand, WorstStatCommand, ChampionCommand,
        MatchHistoryCommand, RankCommand,
    )
    from intfar.discbot.commands.misc import SummaryCommand, PerformanceCommand, WinrateCommand
    from intfar.discbot.commands.intfar import IntfarCommand, IntfarRelationsCommand
    from intfar.discbot.commands.doinks import DoinksCommand, DoinksRelationsCommand
    from intfar.discbot.commands.meta import StatusCommand, UsageCommand


@pytest.fixture(params=["lol", "cs2"])
def database(request, tmp_path):
    game = request.param
    config = SimpleNamespace(
        database_folder=str(tmp_path), schema_folder=str(ROOT / "resources/schemas"),
        performance_mimimum_games=1, hour_of_ifotm_announce=12, ifotm_min_games=1, betting_tokens="tokens",
    )
    database_class = LoLGameDatabase if game == "lol" else CS2GameDatabase
    db = database_class(game, config)
    for person in range(1, 4):
        params = {"player_id": str(person), "player_name": f"Player {person}"}
        if game == "cs2":
            params.update(match_auth_code="test", latest_match_token="test")
        db.add_user(person, **params)

    with db:
        for year in (2024, 2025, 2026):
            for index in range(12):
                game_id = f"{year}{index:04d}"
                timestamp = int(datetime(year, 2, index + 1, tzinfo=STATS_TIMEZONE).timestamp())
                columns = "game_id, timestamp, duration, win, guild_id, intfar_id, intfar_reason"
                values = [game_id, timestamp, 1800, 1 if index % 2 else -1, 1, 1, "1000"]
                if game == "lol":
                    columns += ", first_blood"
                    values.append(1 if index % 2 else 2)
                else:
                    columns += ", map_id, rounds_us, rounds_them"
                    values.extend(["inferno", 16, 14])
                placeholders = ", ".join("?" for _ in values)
                db.execute_query(f"INSERT INTO games ({columns}) VALUES ({placeholders})", *values)
                for person in (1, 2):
                    kills = 100 if year == 2024 and person == 1 else 5 * person
                    if year == 2025 and person == 1 and index == 0:
                        kills = 50
                    columns = "game_id, player_id, kills, deaths, assists, kda, kp, doinks"
                    values = [game_id, str(person), kills, 2, 4, (kills + 4) / 2, 50, "1000000000"]
                    if game == "lol":
                        columns += ", champ_id, role, damage, cs, cs_per_min, gold, vision_score, vision_wards, rank_solo, rank_flex"
                        values.extend([1, "mid", 10000, 100, 5, 10000, 15, 2, "gold_II_25", "silver_II_10"])
                    else:
                        columns += ", rank"
                        values.append(10)
                    placeholders = ", ".join("?" for _ in values)
                    db.execute_query(f"INSERT INTO participants ({columns}) VALUES ({placeholders})", *values)
    return db


@pytest.fixture
def bot(database):
    api = SimpleNamespace(
        get_playable_name=lambda _: "Annie" if database.game == "lol" else "Inferno",
        try_find_playable_id=lambda name: 1 if name.lower() == "annie" else ("inferno" if name.lower() == "inferno" else None),
        get_champ_name=lambda _: "Annie", get_map_name=lambda _: "Inferno", playable_count=10,
        map_names={"inferno": "Inferno"},
    )
    client = SimpleNamespace(
        game_databases={database.game: database}, api_clients={database.game: api},
        meta_database=SimpleNamespace(all_users={1: SimpleNamespace(default_game=database.game)}, get_sounds=lambda _: []),
        get_discord_nick=lambda person, _: f"Player {person}",
        try_get_user_data=lambda name, _: {"player 2": 2, "idle": 3}.get(name),
        insert_emotes=lambda text: text, get_emoji_by_name=lambda _: "",
        get_mention_str=lambda *_: "admin", config=database.config,
        paginate=AsyncMock(), send_message_in_chunks=AsyncMock(),
        time_initialized=datetime(2024, 1, 1),
        audio_handler=SimpleNamespace(get_sounds=lambda _: []),
    )
    message = SimpleNamespace(
        author=SimpleNamespace(id=1, is_on_mobile=lambda: False),
        guild=SimpleNamespace(id=1), channel=SimpleNamespace(send=AsyncMock()),
    )
    return client, message


def run(command_class, bot, args, name=None):
    client, message = bot
    message.channel.send.reset_mock()
    command = command_class(client, message, name or command_class.NAME)
    asyncio.run(command(args.split()))
    messages = [call.args[0] for call in message.channel.send.call_args_list]
    assert not any("error occurred" in text or "querying the database" in text for text in messages), messages
    return command, "\n".join(messages)


def test_year_uses_copenhagen_calendar():
    with freeze_time("2025-12-31 23:30:00+00:00"):
        assert StatPeriod.from_token("year") == StatPeriod(2026)
    assert StatPeriod.from_token("2025") == StatPeriod(2025)
    assert StatPeriod.from_token("all") is None


def test_year_boundaries_and_isolation(database):
    start, end = StatPeriod(2025).timestamps
    with database:
        # Move existing games exactly onto both boundaries.
        database.execute_query("UPDATE games SET timestamp = ? WHERE game_id = ?", start, "20250000")
        database.execute_query("UPDATE games SET timestamp = ? WHERE game_id = ?", end, "20250011")
    year_db = database.for_period(StatPeriod(2025))
    assert year_db.get_games_count(1)[0] == 11
    assert database.get_games_count(1)[0] == 36
    assert year_db.get_most_extreme_stat("kills")[1] == 50
    assert database.get_most_extreme_stat("kills")[1] == 100
    assert year_db.get_doinks_count(1) == (11, 11)
    assert year_db.get_intfar_stats(1)[0] == 11
    with year_db:
        assert year_db.execute_query("SELECT COUNT(*) FROM participants").fetchone()[0] == 22
        with pytest.raises(sqlite3.OperationalError):
            year_db.connection.execute("DELETE FROM main.games")
    assert database.get_games_count(1)[0] == 36


def test_averages_and_rankings_use_same_period(database):
    year_db = database.for_period(StatPeriod(2025))
    assert year_db.get_average_stat("kills", 1)()[0][1:] == (8.75, 12)
    assert database.get_average_stat("kills", 1)()[0][2] == 36
    assert year_db.get_best_or_worst_stat("kills", 1)()[:3] == (1, 12, 50)
    played_id, played_count = year_db.get_played_count_for_stat("kills", True, 1)
    assert played_count == 1
    assert year_db.get_performance_score(1)()[2] == 2
    if database.game == "lol":
        assert year_db.get_average_stat_rank("kills", 1, 1, 2, min_games=1)()[0] == 2
        assert database.get_average_stat_rank("kills", 1, 1, 2, min_games=1)()[0] == 1
        assert year_db.get_best_or_worst_stat("first_blood", 1)()[:2] == (6, 12)


def test_average_default_year_named_target_and_all(bot, database):
    _, text = run(AverageCommand, bot, "kills")
    assert "**36** games" in text and "Stats for" not in text
    _, text = run(AverageCommand, bot, "kills 2025")
    assert "Stats for 2025" in text and "**8.75**" in text and "**12** games" in text
    _, text = run(AverageCommand, bot, "kills Player 2 2025")
    assert "Player 2 averages **10.00**" in text
    _, text = run(AverageCommand, bot, "kills all 2025")
    assert "Player 1" in text and "Player 2" in text
    with freeze_time("2025-06-01"):
        _, text = run(AverageCommand, bot, "kills year")
    assert "Stats for 2025" in text


@pytest.mark.parametrize("command_class", [BestStatCommand, WorstStatCommand])
def test_records_and_all_players(bot, command_class):
    _, text = run(command_class, bot, "kills all 2025")
    assert "Stats for 2025" in text and "ever" not in text


def test_personal_records_use_period_counts(bot):
    _, text = run(BestStatCommand, bot, "kills 2025")
    assert "**1** times out of **12**" in text
    assert "**50**" in text and "**100**" not in text


def test_match_history_filters_every_page(bot):
    run(MatchHistoryCommand, bot, "2025")
    args = bot[0].paginate.call_args.args
    assert len(args[1]) == 12
    assert "Stats for 2025" in args[4]
    assert all("2025/" in row and "2024/" not in row and "2026/" not in row for row in args[1])


def test_playable_and_role_filters(bot, database):
    playable = "annie" if database.game == "lol" else "inferno"
    _, text = run(AverageCommand, bot, f"kills {database.game} {playable} Player 2 2025")
    assert "Stats for 2025" in text and "Player 2 averages **10.00**" in text
    if database.game == "lol":
        _, text = run(ChampionCommand, bot, "annie mid Player 2 2025")
        assert "Player 2" in text and "**12** games" in text


@pytest.mark.parametrize("command_class,args", [
    (AverageCommand, "kills idle 2025"), (BestStatCommand, "kills idle 2025"),
    (DoinksCommand, "idle 2025"), (IntfarCommand, "idle 2025"),
    (SummaryCommand, "idle 2025"), (DoinksRelationsCommand, "idle 2025"),
    (IntfarRelationsCommand, "idle 2025"),
])
def test_player_without_games(bot, command_class, args):
    _, text = run(command_class, bot, args)
    assert "Stats for 2025" in text


def test_independent_period_connections(database):
    old = database.for_period(StatPeriod(2024))
    recent = database.for_period(StatPeriod(2025))
    with database, old, recent:
        assert len({id(db.connection) for db in (database, old, recent)}) == 3
        assert old.get_average_stat("kills", 1)()[0][1] == 100
        assert recent.get_average_stat("kills", 1)()[0][1] == 8.75
        assert database.get_games_count(1)[0] == 36
    assert not old._connections and not recent._connections and not database._connections


def test_reusing_command_restores_all_time(bot):
    client, message = bot
    command = AverageCommand(client, message, "average")
    asyncio.run(command(["kills", "2025"]))
    assert "Stats for 2025" in message.channel.send.call_args.args[0]
    asyncio.run(command(["kills"]))
    text = message.channel.send.call_args.args[0]
    assert "Stats for" not in text and "**36** games" in text


def test_rank_uses_historical_participants_instead_of_current_user(database):
    if database.game == "lol":
        with database:
            database.execute_query("UPDATE users SET rank_solo = 'diamond_I_50', rank_flex = 'diamond_II_10'")
        assert database.get_current_rank("1") == ("diamond_I_50", "diamond_II_10")
        assert database.for_period(StatPeriod(2025)).get_current_rank("1") == ("gold_II_25", "silver_II_10")
    else:
        with database:
            database.execute_query("UPDATE participants SET rank = 18 WHERE game_id LIKE '2026%'")
        assert database.get_current_rank("1") == (18,)
        assert database.for_period(StatPeriod(2025)).get_current_rank("1") == (10,)


def test_rank_command_for_each_game(bot, database):
    queue = "solo" if database.game == "lol" else "premier"
    _, text = run(RankCommand, bot, f"{queue} 2025")
    assert "Stats for 2025" in text and "latest recorded rank" in text


def test_minimum_games_counts_only_selected_year(bot, database):
    with database:
        database.execute_query("DELETE FROM games WHERE game_id LIKE '2025%' AND game_id > '20250003'")
    _, text = run(AverageCommand, bot, "kills 2025")
    assert "Stats for 2025" in text and "not yet played at least 10 games" in text
    _, text = run(AverageCommand, bot, "kills")
    assert "**28** games" in text


def test_status_filters_sound_uploads_by_exact_calendar_boundary(bot):
    start, end = StatPeriod(2025).timestamps
    bot[0].meta_database.get_sounds = lambda _: [
        ("old", 1, 0, start - 1), ("included", 2, 0, start), ("new", 3, 0, end),
    ]
    _, text = run(StatusCommand, bot, "2025")
    assert "**1** sounds have been uploaded by **1** people" in text


@pytest.mark.parametrize("command_class,args", [
    (IntfarCommand, "2025"), (IntfarCommand, "all 2025"),
    (DoinksCommand, "2025"), (DoinksCommand, "all 2025"),
    (IntfarRelationsCommand, "2025"), (DoinksRelationsCommand, "2025"),
    (PerformanceCommand, "2025"), (PerformanceCommand, "all 2025"),
    (StatusCommand, "2025"),
])
def test_other_stat_commands(bot, command_class, args):
    _, text = run(command_class, bot, args)
    assert "Stats for 2025" in text
    assert "All time" not in text


def test_summary_and_winrate(bot, database):
    _, text = run(SummaryCommand, bot, "2025")
    chunks = bot[0].send_message_in_chunks.call_args.args[1]
    assert "Stats for 2025" in chunks and "**12** games" in chunks
    playable = "annie" if database.game == "lol" else "inferno"
    _, text = run(WinrateCommand, bot, f"{playable} 2025")
    assert "Stats for 2025" in text and "**12** games" in text


def test_champion_and_historical_rank(bot, database):
    if database.game != "lol":
        pytest.skip("Champion command is specific to LoL")
    _, text = run(ChampionCommand, bot, "annie 2025")
    assert "Stats for 2025" in text and "**12** games" in text
    _, text = run(RankCommand, bot, "solo 2025")
    assert "Stats for 2025" in text and "Gold II" in text


@pytest.mark.parametrize("command_class,args", [
    (AverageCommand, "kills 2023"), (BestStatCommand, "kills all 2023"),
    (IntfarCommand, "2023"), (DoinksCommand, "all 2023"),
    (SummaryCommand, "2023"), (PerformanceCommand, "2023"),
    (MatchHistoryCommand, "2023"), (StatusCommand, "2023"),
])
def test_empty_year(bot, command_class, args):
    _, text = run(command_class, bot, args)
    assert "No games recorded" in text and "2023" in text


def test_alias_and_usage(bot, monkeypatch):
    monkeypatch.setitem(command_util.COMMANDS, "average", AverageCommand)
    monkeypatch.setattr(AverageCommand, "GUILDS", [1])
    client, message = bot
    command = get_handler("avg", client, message)
    asyncio.run(command(["kills", "2025"]))
    assert "Stats for 2025" in message.channel.send.call_args.args[0]
    _, text = run(UsageCommand, bot, "avg")
    assert "(year/YYYY)" in text and "all time by default" in text


def test_invalid_year_and_missing_stat(bot):
    _, text = run(AverageCommand, bot, "kills 0000")
    assert "Choose a year" in text
    _, text = run(AverageCommand, bot, "year")
    assert "Usage:" in text
