import asyncio
import pytest

from intfar.api.game_monitors import get_game_monitor
from intfar.api.util import SUPPORTED_GAMES, GUILD_MAP
from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_database import GameDatabase
from intfar.api.game_api_client import GameAPIClient

@pytest.mark.asyncio
async def test_polling_start(
    config: Config,
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    api_clients: dict[str, GameAPIClient]
):
    guild_id = GUILD_MAP["core"]

    for game in SUPPORTED_GAMES:
        game_monitor = get_game_monitor(game, config, meta_database, game_databases[game], api_clients[game])
        game_monitor.config.status_interval_dormant = 5
        users = [
            game_databases[game].game_user_data_from_discord_id(2),
            game_databases[game].game_user_data_from_discord_id(3),
        ]

        for index, user in enumerate(users):
            game_monitor.add_user_in_voice_channel(user, guild_id, True)

            assert len(game_monitor.users_in_voice[guild_id]) == index + 1
            assert game_monitor.polling_active.get(guild_id, False) is (index == 1)

            if index == 1:
                assert game_monitor.polling_tasks[guild_id] is not None

        await game_monitor.stop_polling(guild_id)
        await game_monitor.polling_tasks[guild_id]

@pytest.mark.asyncio
async def test_polling_stop_immediately(
    config: Config,
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    api_clients: dict[str, GameAPIClient]
):
    guild_id = GUILD_MAP["core"]

    for game in SUPPORTED_GAMES:
        game_monitor = get_game_monitor(game, config, meta_database, game_databases[game], api_clients[game])
        game_monitor.config.status_interval_dormant = 5
        game_monitor.polling_stop_delay = 0
        users = [
            game_databases[game].game_user_data_from_discord_id(2),
            game_databases[game].game_user_data_from_discord_id(3),
        ]

        for index, user in enumerate(users):
            game_monitor.add_user_in_voice_channel(user, guild_id, True)

            assert len(game_monitor.users_in_voice[guild_id]) == index + 1
            assert game_monitor.polling_active.get(guild_id, False) is (index == 1)

            if index == 1:
                assert game_monitor.polling_tasks.get(guild_id) is not None

        await game_monitor.remove_user_from_voice_channel(users[0], guild_id)

        # Assert polling has stopped
        assert len(game_monitor.users_in_voice[guild_id]) == 1
        assert not game_monitor.polling_active[guild_id]

        await game_monitor.polling_tasks[guild_id]

@pytest.mark.asyncio
async def test_polling_stop_after_delay(
    config: Config,
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    api_clients: dict[str, GameAPIClient]
):
    guild_id = GUILD_MAP["core"]

    for game in SUPPORTED_GAMES:
        game_monitor = get_game_monitor(game, config, meta_database, game_databases[game], api_clients[game])
        game_monitor.config.status_interval_dormant = 5
        game_monitor.polling_stop_delay = 3
        users = [
            game_databases[game].game_user_data_from_discord_id(2),
            game_databases[game].game_user_data_from_discord_id(3),
        ]

        for index, user in enumerate(users):
            game_monitor.add_user_in_voice_channel(user, guild_id, True)

            assert len(game_monitor.users_in_voice[guild_id]) == index + 1
            assert game_monitor.polling_active.get(guild_id, False) is (index == 1)

            if index == 1:
                assert game_monitor.polling_tasks.get(guild_id) is not None

        await game_monitor.remove_user_from_voice_channel(users[0], guild_id)

        # Assert polling has not yet stopped
        assert len(game_monitor.users_in_voice[guild_id]) == 2
        assert game_monitor.polling_active[guild_id]
        assert game_monitor.polling_tasks.get(guild_id) is not None

        await asyncio.sleep(4)

        # Assert polling has stopped after a delay
        assert len(game_monitor.users_in_voice[guild_id]) == 1
        assert not game_monitor.polling_active[guild_id]

        await game_monitor.polling_tasks[guild_id]
