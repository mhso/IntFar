from argparse import ArgumentParser
from datetime import datetime

import freezegun

from intfar.api.game_apis import get_api_client
from intfar.api.game_databases import get_database_client
from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.discbot.discord_bot import DiscordClient
from intfar.discbot.montly_intfar import MonthlyIntfar
from intfar.api.util import SUPPORTED_GAMES

async def announce_ifotm(client, game):
    dt = datetime.now()
    dt = dt.replace(hour=client.config.hour_of_ifotm_announce, minute=0, second=0, microsecond=0)
    ifotm_monitor = MonthlyIntfar(client.config.hour_of_ifotm_announce)
    ifotm_monitor.time_at_announcement = ifotm_monitor.time_at_announcement.replace(year=dt.year, month=dt.month)

    with freezegun.freeze_time(dt):
        await client.declare_monthly_intfar(game, ifotm_monitor)

if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("game", type=str, choices=SUPPORTED_GAMES.keys())

    args = parser.parse_args()

    config = Config()
    meta_database = MetaDatabase(config)
    game_databases = {game: get_database_client(game, config) for game in SUPPORTED_GAMES}
    betting_handlers = {}
    api_clients = {game: get_api_client(game, config) for game in SUPPORTED_GAMES}

    client = DiscordClient(config, meta_database, game_databases, betting_handlers, api_clients)
    client.add_event_listener("ready", announce_ifotm, client, args.game)

    client.run(config.discord_token)
