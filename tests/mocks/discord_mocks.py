from src.discbot.discord_bot import DiscordClient

class MockDiscordClient(DiscordClient):
    pass

class MockMessage:
    pass

class MockChannel:
    def __init__(self) -> None:
        self.messages_sent = []

    async def send(self, message: str):
        self.messages_sent.append(message)
