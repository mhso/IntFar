import asyncio
import json
from sys import argv
from api.database import Database
from api.bets import BettingHandler
from discbot.discord_bot import DiscordClient
from api.config import Config
from api.riot_api import APIClient

class MockChannel:
    async def send(self, data):
        await asyncio.sleep(0.1)

class TestMock(DiscordClient):
    def __init__(self, config, database, betting_handler, riot_api):
        super().__init__(config, database, betting_handler, riot_api, None, flask_conn=None)
        if len(argv) != 4:
            print("Wrong number of arguments.")
            print("Must supply: [game_id, task, loud] where task in ('all', 'bets', 'stats')")
            exit(0)

        self.game_id = int(argv[1])
        self.task = argv[2]
        self.loud = argv[3] == "True"

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        d1, sm1, si1 = self.database.discord_id_from_summoner("senile felines")
        d2, sm2, si2 = self.database.discord_id_from_summoner("nønø")
        d3, sm3, si3 = self.database.discord_id_from_summoner("criller")
        self.users_in_game = [
            (d1, sm1, si1),
            (d2, sm2, si2),
            (d3, sm3, si3)
        ]
        self.active_game = {"id": self.game_id}
        game_info = self.riot_api.get_game_details(self.game_id)
        filtered = self.get_filtered_stats(game_info)

        if self.loud:
            betting_data = await self.declare_intfar(filtered)
        else:
            betting_data = self.get_intfar_and_doinks(filtered)

        if betting_data is not None:
            intfar, intfar_reason, doinks = betting_data
            await asyncio.sleep(1)
            if self.task in ("all", "bets"):
                if not self.loud:
                    self.channel_to_write = MockChannel()

                await self.resolve_bets(filtered, intfar, intfar_reason, doinks)

            if self.task in ("all", "stats"):
                await self.save_stats(filtered, intfar, intfar_reason, doinks)

    def get_intfar_and_doinks(self, filtered_stats):
        intfar_details = self.get_intfar_details(filtered_stats, filtered_stats[0][1]["mapId"])
        (intfar_data,
         max_count_intfar,
         max_intfar_count) = self.get_intfar_qualifiers(intfar_details)
        reason_ids = ["0", "0", "0", "0"]
        final_intfar = None

        if max_count_intfar is not None: # Send int-far message.
            final_intfar = self.resolve_intfar_ties(intfar_data, max_intfar_count, filtered_stats)

            # Go through the criteria the chosen Int-Far met and list them in a readable format.
            for (reason_index, _) in intfar_data[final_intfar]:
                reason_ids[reason_index] = "1"

        _, doinks = self.get_big_doinks(filtered_stats)

        reasons_str = "".join(reason_ids)
        if reasons_str == "0000":
            reasons_str = None

        return final_intfar, reasons_str, doinks

GAME_ID = 5015736026

auth = json.load(open("discbot/auth.json"))

conf = Config()
conf.env = auth["env"]

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

riot_api = APIClient(conf)

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

bet_client = BettingHandler(conf, database_client)

client = TestMock(conf, database_client, bet_client, riot_api)

client.run(conf.discord_token)
