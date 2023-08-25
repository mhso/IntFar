import inspect
from multiprocessing import Pipe
from multiprocessing.connection import wait
from threading import Thread, Event

class Proxy(object):
    def __init__(self, conn):
        self.conn = conn

    @property
    def game(self):
        return self._call_proxy("game")

    @property
    def config(self):
        return self._call_proxy("config")

    def _call_proxy(self, command, *args):
        self.conn.send((command, *args))
        return self.conn.recv()

    def parse_demo(self, demo_url):
        return self._call_proxy("parse_demo", demo_url)

    def get_game_details(self, match_token):
        return self._call_proxy("get_game_details", match_token)

    def get_active_game(self, steam_ids):
        return self._call_proxy("get_active_game", steam_ids)

    def get_next_sharecode(self, steam_id, game_code, match_token):
        return self._call_proxy("get_next_sharecode", steam_id, game_code, match_token)

    def get_steam_display_name(self, steam_id):
        return self._call_proxy("get_steam_display_name", steam_id)

    def send_friend_request(self, steam_id):
        return self._call_proxy("send_friend_request", steam_id)

    def get_2fa_code_from_secrets(self):
        return self._call_proxy("get_2fa_code_from_secrets")

    def login(self):
        return self._call_proxy("login")

    def close(self):
        res = self._call_proxy("close")
        self.conn.close()
        return res

class Manager(object):
    def __init__(self, target, *args):
        self.proxies = []

        for target_cls in [target, super(target)]:
            for attr in dir(target_cls):
                if not attr.startswith("__"):
                    if inspect.isfunction(getattr(target_cls, attr)):
                        setattr(
                            Proxy,
                            attr,
                            lambda s: object.__getattribute__(s, '_call_proxy')(attr)
                        )
                    else:
                        print("No")
                        print(attr)
                        setattr(Proxy, attr, object.__getattribute__(target_cls, attr))

        self.target = target(*args)
        self._stop_event = Event()
        self.listen_thread = Thread(target=self._listen, args=())
        self.listen_thread.start()

    def _listen(self):
        while not self._stop_event.is_set():
            for proxy in wait(self.proxies, timeout=0.01):
                command, *args = proxy.recv()

                if command == "close":
                    proxy.send("exiting...")
                    break

                try:
                    result = getattr(self.target, command)
                    if callable(result):
                        result = result(*args)
                except AttributeError:
                    return proxy.send(None)

                proxy.send(result)

    def create_proxy(self):
        conn_1, conn_2 = Pipe(True)
        self.proxies.append(conn_1)
        return Proxy(conn_2)

    def close(self):
        self._stop_event.set()
