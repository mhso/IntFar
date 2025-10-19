import pytest

from src.discbot.discord_mocks import *
from tests.commands import get_games

@pytest.mark.asyncio
async def test_betting(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]

    for game in get_games():
        channel.messages_sent = []
        game = await discord_client.call_command(
            "!doinks [game]",
            member,
            channel,
            guild,
            2,
            game
        )

        expected_output = [
            
        ]

        assert channel.messages_sent == expected_output, "Wrong content of sent messages"
