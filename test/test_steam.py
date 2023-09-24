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
        self.steam_process = None
        self.steam_2fa_code = None
        self.before_all(config=conf, database=db)

    def before_all(self, **test_args):
        super().before_all(**test_args)

        self.steam_2fa_code = input("Steam 2FA Code: ")
        self.steam_process = subprocess.Popen(
            f". venv/Scripts/activate; python run_steam.py csgo {self.steam_2fa_code}",
            executable="C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            text=True
        )

    def after_all(self):
        self.steam_process.kill()

        while self.steam_process.poll() is None:
            sleep(0.1)

    def _send_cmd(self, command, *args):
        serialized_cmd = f"{command}:{';'.join(map(str, args))}\n"

        self.steam_process.stdin.write(serialized_cmd)
        self.steam_process.stdin.flush()

        result = self.steam_process.stdout.readline()
    
        if result.endswith("\n"):
            result = result.strip()

        return result.split(":")

    @test
    def test_get_map_name(self):
        dtype, *values = self._send_cmd("get_map_name", "dust2")

        self.assert_equals(dtype, "str", "Correct dtype")
        self.assert_equals(len(values), 1, "Correct length of return values")
        self.assert_equals(values[0], "Dust II", "Correct map name")

    @test
    def get_match_info(self):
        match_token = "CSGO-EAcYr-PnXWK-CfHHM-WyofA-8TryM"

        dtype, *values = self._send_cmd("get_game_details", match_token)

        print(dtype, values)

        self.assert_equals(dtype, "json", "Correct dtype")
