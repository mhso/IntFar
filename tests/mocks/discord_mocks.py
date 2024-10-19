class MockDiscordClient:
    async def insert_emotes(self):
        pass

class MockChannel:
    def __init__(self):
        self.messages_sent = []

    async def send(self, message: str):
        self.messages_sent.append(message)

class MockMessage:
    def __init__(self, channel: MockChannel):
        self.channel = channel
