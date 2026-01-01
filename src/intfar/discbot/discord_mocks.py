from uuid import uuid4
from typing import List
from intfar.api.util import MAIN_GUILD_ID
from intfar.discbot.discord_bot import DiscordClient, MAIN_CHANNEL_ID

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
        self.roles = []
        self.messages_sent = []

    async def send(self, content: str):
        print("User DM:")
        print(content)
        self.messages_sent.append(content)

    async def add_roles(self, *roles):
        for role in roles:
            self.roles.append(role)

    def is_on_mobile(self):
        return False

    @property
    def display_name(self):
        return self.name

    @property
    def mention(self):
        return f"@{self.name}"

CLIENT_USER = MockUser(133742, "Int-Far Daddy")

class MockChannel:
    def __init__(self, name: str, members: List[MockUser], channel_id: int = MAIN_CHANNEL_ID):
        self.name = name
        self.members = members
        self.id = channel_id
        self.messages_sent = []
        self.guild = None

    async def send(self, content: str):
        print("Channel message:")
        print(content)
        message = MockMessage(content, CLIENT_USER, self, self.guild)
        self.messages_sent.append(message)

        return message

class MockRole:
    def __init__(self, role_id: int, name: str, color: tuple):
        self.id = role_id
        self.name = name
        self.color = color

class MockGuild:
    def __init__(self, name: str, members: List[MockUser], channels: List[MockChannel], guild_id: int = MAIN_GUILD_ID):
        self.name = name
        self.members = members
        self.id = guild_id
        self.roles = []
        self._channels = channels

    @property
    def text_channels(self):
        return self._channels

    def get_member(self, user_id):
        for member in self.members:
            if member.id == user_id:
                return member
            
        return None

    def get_channel(self, channel_id):
        for channel in self.text_channels:
            if channel.id == channel_id:
                return channel

        return None

    async def create_role(self, name, color):
        self.roles.append(MockRole(len(self.roles), name, color))

class MockMessage:
    def __init__(self, content: str, author: MockUser, channel: MockChannel, guild: MockGuild):
        self.id = uuid4()
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild

    async def add_reaction(self, emoji):
        pass

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
        self._user = CLIENT_USER

    @property
    def guilds(self):
        return self._guilds

    @property
    def user(self):
        return self._user

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
    ):
        message = MockMessage(command, author, channel, guild)
        await self.on_message(message, True)

        return message
