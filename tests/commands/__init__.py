from src.api.util import SUPPORTED_GAMES
from src.api.meta_database import DEFAULT_GAME
from src.discbot.discord_mocks import MockDiscordClient, MockUser, MockGuild, MockChannel

def get_games():
    games = [game for game in SUPPORTED_GAMES if game != DEFAULT_GAME]
    games.append(None)

    return games

async def call_command(
    command: str,
    client: MockDiscordClient,
    author: MockUser,
    channel: MockChannel,
    guild: MockGuild,
    expected_messages: int,
    game: str = None,
):
    if not game:
        game = ""
    else:
        game = " " + game

    command = command.replace(" [game]", game)

    await client.call_command(command, author, channel, guild)

    assert len(channel.messages_sent) == expected_messages, "Wrong number of messages sent"
    for message in channel.messages_sent:
        assert len(message) < 2000, "Length of sent message is too long"

    if not game:
        game = DEFAULT_GAME

    return game.strip()
