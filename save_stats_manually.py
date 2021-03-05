import asyncio
import json
import argparse
from api import award_qualifiers
from api.database import Database
from api.bets import BettingHandler
from discbot.discord_bot import DiscordClient, ADMIN_DISC_ID
from api.config import Config
from api.riot_api import APIClient
from api.game_stats import get_filtered_stats
from api.util import GUILD_IDS, create_predictions_timeline_image

GUILDS = {
    "nibs": GUILD_IDS[0],
    "circus": GUILD_IDS[1],
    "core": GUILD_IDS[2]
}

class MockChannel:
    async def send(self, data):
        await asyncio.sleep(0.1)

class TestMock(DiscordClient):
    def __init__(self, args, config, database, betting_handler, riot_api):
        super().__init__(config, database, betting_handler, riot_api)
        self.game_id = args.game_id
        self.guild_to_use = GUILDS[args.guild_name]
        self.task = args.task
        self.loud = not args.silent

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        self.active_game[self.guild_to_use] = {"id": self.game_id}
        game_info = self.riot_api.get_game_details(self.game_id)
        self.active_game[self.guild_to_use]["queue_id"] = game_info["queueId"]

        filtered, users_in_game = get_filtered_stats(
            self.database, [], game_info
        )

        self.users_in_game[self.guild_to_use] = users_in_game

        if self.loud:
            betting_data = await self.declare_intfar(filtered, self.guild_to_use)
        else:
            betting_data = self.get_intfar_and_doinks(filtered)

        if betting_data is not None:
            intfar, intfar_reason, doinks = betting_data
            await asyncio.sleep(1)
            if self.task in ("all", "bets"):
                if not self.loud:
                    self.channels_to_write[self.guild_to_use] = MockChannel()

                await self.resolve_bets(filtered, intfar, intfar_reason, doinks, self.guild_to_use)

            if self.task in ("all", "stats"):
                await self.save_stats(filtered, intfar, intfar_reason, doinks, self.guild_to_use)

        predictions_img = None
        for disc_id, _, _ in users_in_game:
            if ADMIN_DISC_ID == disc_id:
                predictions_img = create_predictions_timeline_image()
                break

        if predictions_img is not None:
            await self.send_predictions_timeline_image(predictions_img, self.guild_to_use)

    def get_intfar_and_doinks(self, filtered_stats):
        (final_intfar, final_intfar_data,
         ties, tie_desc) = award_qualifiers.get_intfar(filtered_stats, self.config)

        doinks = award_qualifiers.get_big_doinks(filtered_stats)[1]

        reason_ids = ["0", "0", "0", "0"]
        if final_intfar is not None: # Send int-far message.
            for (reason_index, _) in final_intfar_data:
                reason_ids[reason_index] = "1"

        reasons_str = "".join(reason_ids)
        if reasons_str == "0000":
            reasons_str = None

        return final_intfar, reasons_str, doinks

parser = argparse.ArgumentParser()

parser.add_argument("game_id", type=int)
parser.add_argument("guild_name", type=str, choices=GUILDS)
parser.add_argument("task", type=str, choices=("all", "bets", "stats"))
parser.add_argument("-s", "--silent", action="store_true")

args = parser.parse_args()

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

client = TestMock(args, conf, database_client, bet_client, riot_api)

client.run(conf.discord_token)
