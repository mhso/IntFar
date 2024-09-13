import inspect
import subprocess
import json
import asyncio
from time import sleep
from multiprocessing import Pipe
from multiprocessing.connection import wait
from threading import Thread, Event

from mhooge_flask.logging import logger

from api.config import Config
from api.meta_database import MetaDatabase

class Proxy(object):
    def __init__(self, conn, target_cls):
        self.conn = conn
        self.target_cls = target_cls

        self._set_attributes()

    def _set_attributes(self):
        for attr in dir(self.target_cls):
            if not attr.startswith("__"):
                if asyncio.iscoroutinefunction(getattr(self.target_cls, attr)):
                    async def call(*args, x=attr):
                        return self.__getattribute__("_call_proxy")(x, *args)

                    setattr(self, attr, call)

                elif inspect.isfunction(getattr(self.target_cls, attr)):
                    def call(*args, x=attr):
                        return self.__getattribute__("_call_proxy")(x, *args)
    
                    setattr(self, attr, call)

    def __getattr__(self, name):
        return self._call_proxy(name)

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

        executable = "/bin/bash" if config.env == "production" else "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"

        self.steam_process = subprocess.Popen(
            f"pdm run run_steam.py {game}",
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

                    if self.steam_process.poll() is not None:
                        # Steam process isn't running, no point in sending commands
                        proxy.send(None)
                        continue

                    result = None
                    self.database.enqueue_command(command_id, self.target_name, command, *args)

                    if command == "close":
                        proxy.send("exiting...")
                        break

                    wait_time = 0
                    while wait_time < timeout:
                        result, done = self.database.get_command_result(command_id, self.target_name)

                        if done:
                            break

                        wait_time += time_to_sleep
                        sleep(time_to_sleep)

                    proxy.send(result)
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
            logger.info("Shutting down Steam process...")
            try:
                # Try to shut down steam process gracefully via a command
                self.database.enqueue_command(-1, self.target_name, "close")

                max_sleep = 10
                time_slept = 0
                interval = 0.1
                while self.steam_process.poll() is None and time_slept < max_sleep:
                    sleep(interval)
                    time_slept += interval

            except Exception:
                pass

            finally:
                if self.steam_process.poll() is None:
                    # Diplomacy failed, seems we have to do things the hard away!
                    logger.info("Killing Steam process...")
                    self.steam_process.kill()
