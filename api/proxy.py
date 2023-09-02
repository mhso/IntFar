import inspect
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

class Manager(object):
    def __init__(self, target_cls, *args):
        self.proxies = []
    
        self.target = target_cls(*args)
    
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
                    proxy.send(None)

                proxy.send(result)

    def create_proxy(self):
        conn_1, conn_2 = Pipe(True)
        self.proxies.append(conn_1)

        proxy = Proxy(conn_2, self.target.__class__)

        return proxy

    def close(self):
        self._stop_event.set()
        if self.proxies:
            self.proxies[0].close()
