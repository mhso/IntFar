from httpx import AsyncClient

class MockResponse:
    def __init__(self) -> None:
        self.status_code = 200
        self.text = ""

    def json(self):
        return {}

class MockAsyncClient(AsyncClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requests_sent = []

    async def request(self, method: str, url: str, **kwargs):
        self.requests_sent.append((method, url))
        return MockResponse()
