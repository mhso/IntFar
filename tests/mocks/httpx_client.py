from httpx import AsyncClient

class MockAsyncClient(AsyncClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requests_sent = []

    def request(self, method: str, url: str, **kwargs):
        self.requests_sent.append((method, url))
