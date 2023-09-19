import subprocess
from time import sleep

from test.runner import TestRunner, test
from api.config import Config
from api.database import Database

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        db = Database(conf)
        self.before_all(config=conf, database=db)

    @test
    def test_get_map_name(self):
        steam_process = subprocess.Popen(
            f". venv/Scripts/activate; python run_steam.py csgo None",
            executable="C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            text=True
        )

        command = "get_map_name"
        args = ["dust2"]

        serialized_cmd = f"{command}:{';'.join(map(str, args))}\n"

        steam_process.stdin.write(serialized_cmd)
        steam_process.stdin.flush()

        result = steam_process.stdout.readline()
        if result.endswith("\n"):
            result = result.strip()

        dtype, *values = result.split(":")

        self.assert_equals(dtype, "str", "Correct dtype")
        self.assert_equals(len(values), 1, "Correct length of return values")
        self.assert_equals(values[0], "Dust II", "Correct map name")

        steam_process.kill()

        while steam_process.poll() is None:
            sleep(0.1)
