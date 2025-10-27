from argparse import ArgumentParser

import asyncio

from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_database import GameDatabase
from intfar.api.game_databases import get_database_client
from intfar.api.bets import get_betting_handler
from intfar.api.util import SUPPORTED_GAMES, MY_GUILD_ID, GUILD_MAP, GUILD_IDS
from intfar.discbot.discord_bot import CHANNEL_IDS, TEST_CHANNLEL_ID
from intfar.discbot.commands.base import handle_command
from intfar.discbot.commands.util import COMMANDS, ADMIN_DISC_ID
from run_discord_bot import initialize_commands
from intfar.discbot.discord_mocks import MockDiscordClient, MockUser, MockGuild, MockChannel
from intfar.api.game_apis.mocks.riot_api import MockRiotAPI
from intfar.api.game_apis.mocks.steam_api import MockSteamAPI

def create_client(config: Config, meta_database: MetaDatabase, game_databases: dict[str, GameDatabase]):
    config.message_timeout = 0

    betting_handlers = {game: get_betting_handler(game, config, meta_database, game_databases[game]) for game in SUPPORTED_GAMES}
    api_clients = {
        "lol": MockRiotAPI("lol", config),
        "cs2": MockSteamAPI("cs2", config)
    }

    client =  MockDiscordClient(
        config,
        meta_database,
        game_databases,
        betting_handlers,
        api_clients
    )
    client.add_event_listener("command", handle_command)

    members = [
        MockUser(disc_id, game_databases["lol"].game_users[disc_id].player_name[0])
        for disc_id in meta_database.all_users
        if disc_id in game_databases["lol"].game_users
    ]

    if TEST_CHANNLEL_ID not in CHANNEL_IDS:
        CHANNEL_IDS.append(TEST_CHANNLEL_ID)

    guilds = []
    for index, guild_id in enumerate(GUILD_IDS, start=1):
        channels = [
            MockChannel("Test channel 1", members, CHANNEL_IDS[index-1]),
            MockChannel("Test channel 2", members, 1337),
        ]
        guild = MockGuild(f"Test guild {index}", members, channels, guild_id)
        for channel in channels:
            channel.guild = guild

        guilds.append(guild)

    channels = [MockChannel("Test channel", [members[0]])]
    guild = MockGuild(f"Test guild", members, channels, MY_GUILD_ID)
    for channel in channels:
        channel.guild = guild

    guilds.append(guild)

    client._guilds = guilds

    for guild in guilds:
        client.channels_to_write[guild.id] = guild.text_channels[0]

    initialize_commands(config)

    for command in COMMANDS:
        client.command_timeout_lengths[command] = 0

    return client

async def call_command(
    command: str,
    client: MockDiscordClient,
    member: MockUser,
    channel: MockChannel,
    guild: MockGuild
):
    return await client.call_command(command, member, channel, guild)

if __name__ == "__main__":
    parser = ArgumentParser()

    guilds = list(GUILD_MAP) + ["test"]
    members = list(range(2, 7)) + [ADMIN_DISC_ID]
    parser.add_argument("command")
    parser.add_argument("-g", "--guild", type=str, choices=guilds, default="test")
    parser.add_argument("-a", "--author", type=int, choices=members, default=ADMIN_DISC_ID)
    parser.add_argument("-c", "--channel", type=int, choices=CHANNEL_IDS + [1337, 1], default=CHANNEL_IDS[0])

    args = parser.parse_args()

    config = Config()
    meta_database = MetaDatabase(config)
    game_databases = {game: get_database_client(game, config) for game in SUPPORTED_GAMES}

    client = create_client(config, meta_database, game_databases)

    guild = client.get_guild(GUILD_MAP[args.guild] if args.guild != "test" else MY_GUILD_ID)
    member = guild.get_member(args.author)
    channel = guild.get_channel(args.channel)

    message = asyncio.run(call_command(args.command, client, member, channel, guild))

    if not message.channel.messages_sent:
        print("No response.")
        exit(0)
