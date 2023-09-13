import inspect
import subprocess
import json
from time import sleep
from multiprocessing import Pipe
from multiprocessing.connection import wait
from threading import Thread, Event

class Proxy(object):
    def __init__(self, conn, target_cls):
        self.conn = conn
        self.target_cls = target_cls

        self._set_attributes()

    @property
    def game(self):
        return self._call_proxy("game")

    @property
    def config(self):
        return self._call_proxy("config")

    @property
    def map_names(self):
        return self._call_proxy("map_names")

    def _set_attributes(self):
        for attr in dir(self.target_cls):
            if not attr.startswith("__"):
                if inspect.isfunction(getattr(self.target_cls, attr)):
                    def call(*args, x=attr):
                        return self.__getattribute__("_call_proxy")(x, *args)

                    setattr(self, attr, call)

    def __getstate__(self):
        return {"conn": self.conn, "target_cls": self.target_cls}

    def __setstate__(self, state):
        self.__dict__ = {"conn": state["conn"], "target_cls": state["target_cls"]}
        self._set_attributes()

    def _call_proxy(self, command, *args):
        self.conn.send((command, *args))
        return self.conn.recv()

class ProxyManager(object):
    def __init__(self, target_cls, game, config):
        self.proxies = []

        self.target_cls = target_cls

        self.steam_process = subprocess.Popen(
            f". venv/bin/activate; python run_steam.py {game} {config.steam_2fa_code}",
            executable="/bin/bash",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            text=True
        )

        self._stop_event = Event()
        self.listen_thread = Thread(target=self._listen)
        self.listen_thread.start()

    def _listen(self):
        while not self._stop_event.is_set():
            for proxy in wait(self.proxies, timeout=0.01):
                command, *args = proxy.recv()

                if command == "close":
                    proxy.send("exiting...")
                    break

                serialized_cmd = f"{command}: {';'.join(map(str, args))}\n"

                print("Sending:", serialized_cmd, flush=True)

                self.steam_process.stdin.write(serialized_cmd)
                self.steam_process.stdin.flush()

                result = self.steam_process.stdout.readline()
                if result.endswith("\n"):
                    result = result.strip()

                print("Received:", result, flush=True)

                dtype, *values = result.split(":")
                value_str = ":".join(values)
                if dtype == "json":
                    value_str = json.loads(value_str)

                proxy.send(value_str)

    def create_proxy(self):
        conn_1, conn_2 = Pipe(True)
        self.proxies.append(conn_1)

        proxy = Proxy(conn_2, self.target_cls)

        return proxy

    def close(self):
        self._stop_event.set()
        if self.proxies:
            self.proxies[0].close()

        self.steam_process.stdin.write("close")
        self.steam_process.stdin.flush()

        while self.steam_process.returncode is None:
            sleep(0.1)
