from typing import List
from src.api.util import MAIN_GUILD_ID
from src.api.meta_database import DEFAULT_GAME
from src.discbot.discord_bot import DiscordClient, MAIN_CHANNEL_ID

class Emoji:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f":{self.name}:"

class MockUser:
    def __init__(self, disc_id: int, name: str):
        self.id = disc_id
        self.name = name
        self.global_name = name
        self.nick = name
        self.messages_sent = []

    async def send(self, content: str):
        self.messages_sent.append(content)

    @property
    def display_name(self):
        return self.name

    @property
    def mention(self):
        return f"@{self.name}"

class MockChannel:
    def __init__(self, name: str, members: List[MockUser], channel_id: int = MAIN_CHANNEL_ID):
        self.name = name
        self.members = members
        self.id = channel_id
        self.messages_sent = []

    async def send(self, content: str):
        self.messages_sent.append(content)

class MockGuild:
    def __init__(self, name: str, members: List[MockUser], channels: List[MockChannel], guild_id: int = MAIN_GUILD_ID):
        self.name = name
        self.members = members
        self.id = guild_id
        self._channels = channels

    @property
    def text_channels(self):
        return self._channels

class MockMessage:
    def __init__(self, content: str, author: MockUser, channel: MockChannel, guild: MockGuild):
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild

class MockDiscordClient(DiscordClient):
    def __init__(
        self,
        config,
        meta_database,
        game_databases,
        betting_handlers,
        api_clients,
        **kwargs
    ):
        super().__init__(config, meta_database, game_databases, betting_handlers, api_clients, **kwargs)
        self._guilds = []

    @property
    def guilds(self):
        return self._guilds

    def get_guild(self, guild_id: int) -> MockGuild:
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild
            
        return None

    def get_user(self, disc_id: int) -> MockUser:
        for guild in self.guilds:
            for member in guild.members:
                if member.id == disc_id:
                    return member

        return None

    async def send_dm(self, text: str, disc_id: int) -> bool:
        await self.get_user(disc_id).send(text)

    def get_emoji_by_name(self, emoji_name: str):
        return str(Emoji(emoji_name))

    async def call_command(
        self,
        command: str,
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

        if not game:
            game = DEFAULT_GAME

        message = MockMessage(command, author, channel, guild)
        await self.on_message(message)

        assert len(channel.messages_sent) == expected_messages, "Wrong number of messages sent"
        for message in channel.messages_sent:
            assert len(message) < 2000, "Length of sent message is too long"

        return game
