import inspect
import subprocess
import json
from time import sleep
from multiprocessing import Pipe
from multiprocessing.connection import wait
from threading import Thread, Event

from api.config import Config
from api.meta_database import MetaDatabase

class Proxy(object):
    def __init__(self, conn, target_cls):
        self.conn = conn
        self.target_cls = target_cls

        self._set_attributes()

    @property
    def logged_on_once(self):
        return self._call_proxy("logged_on_once")

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
    def __init__(self, target_cls, game: str, meta_database: MetaDatabase, config: Config):
        self.proxies = []
        self.database = meta_database

        self.target_cls = target_cls
        self.target_name = self.target_cls.__name__

        subfolder = "bin" if config.env == "production" else "Scripts"
        executable = "/bin/bash" if config.env == "production" else "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"

        self.steam_process = subprocess.Popen(
            f". ../.venv/{subfolder}/activate; python run_steam.py {game} {config.steam_2fa_code}",
            executable=executable,
            shell=True,
            text=True
        )

        self._stop_event = Event()
        self.listen_thread = Thread(target=self._listen)
        self.listen_thread.start()

    def _listen(self):
        command_id = 0
        timeout = 60
        time_to_sleep = 0.5

        while not self._stop_event.is_set():
            try:
                for proxy in wait(self.proxies, timeout=0.01):
                    try:
                        command, *args = proxy.recv()
                    except (OSError, BrokenPipeError):
                        self.kill()
                        break

                    if command == "close":
                        proxy.send("exiting...")
                        break

                    if self.steam_process.poll() is not None:
                        # Steam process isn't running, no point in sending commands
                        proxy.send(None)
                        continue

                    result = None
                    self.database.enqueue_command(command_id, self.target_name, command, *args)
                    wait_time = 0
                    while wait_time < timeout:
                        result = self.database.get_command_result(command_id, self.target_name)

                        if result is not None:
                            break

                        wait_time += time_to_sleep
                        sleep(time_to_sleep)

                    if result is None:
                        result = "null:None"

                    dtype, *values = result.split(":")
                    if dtype == "null":
                        proxy.send(None)
                    else:
                        value_str = ":".join(values)
                        if dtype == "json":
                            value_str = json.loads(value_str)
                        elif dtype == "int":
                            value_str = int(value_str)
                        elif dtype == "bool":
                            value_str = bool(value_str)
                        else:
                            value_str = str(value_str)

                        proxy.send(value_str)

                    command_id += 1
            except OSError:
                break

    def create_proxy(self):
        conn_1, conn_2 = Pipe(True)
        self.proxies.append(conn_1)

        proxy = Proxy(conn_2, self.target_cls)

        return proxy

    def is_alive(self):
        return not self._stop_event.is_set()

    def kill(self):
        self._stop_event.set()
        for proxy in self.proxies:
            proxy.close()

        if self.steam_process.poll() is None:
            self.database.enqueue_command(-1, self.target_name, "close")

            while self.steam_process.poll() is None:
                sleep(0.1)
