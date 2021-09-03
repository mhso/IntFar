import asyncio
import json
import argparse
from api import award_qualifiers
from api.audio_handler import AudioHandler
from api.bets import BettingHandler
from api.config import Config
from api.database import Database
from api.shop import ShopHandler
from discbot.discord_bot import DiscordClient, ADMIN_DISC_ID
from api.riot_api import APIClient
from api.game_stats import get_filtered_stats
from api.util import GUILD_IDS, create_predictions_timeline_image
from ai.data import shape_predict_data
from ai.train import train_online
from ai.model import Model

GUILDS = {
    "nibs": GUILD_IDS[0],
    "circus": GUILD_IDS[1],
    "core": GUILD_IDS[2]
}

class MockChannel:
    async def send(self, data):
        await asyncio.sleep(0.1)

class TestMock(DiscordClient):
    def __init__(self, args, config, database, betting_handler, riot_api, audio_handler, shop_handler, **kwargs):
        super().__init__(config, database, betting_handler, riot_api, audio_handler, shop_handler, **kwargs)
        self.game_id = args.game_id
        self.guild_to_use = GUILDS[args.guild_name]
        self.task = args.task
        self.loud = not args.silent
        self.play_sound = args.play
        self.ai_model = kwargs.get("ai_model")

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        self.active_game[self.guild_to_use] = {"id": self.game_id}
        game_info = self.riot_api.get_game_details(self.game_id)
        self.active_game[self.guild_to_use]["queue_id"] = game_info["queueId"]

        filtered, users_in_game = get_filtered_stats(
            self.database.summoners, [], game_info
        )

        self.users_in_game[self.guild_to_use] = users_in_game

        if self.loud:
            intfar, intfar_reason, response = self.get_intfar_data(filtered, self.guild_to_use)
        else:
            intfar, intfar_reason, response = self.get_intfar_and_doinks(filtered)

        doinks, doinks_response = self.get_doinks_data(filtered, self.guild_to_use)
        if doinks_response is not None:
            response += "\n" + self.insert_emotes(doinks_response)

        if self.loud and self.task == "all":
            await self.channels_to_write[self.guild_to_use].send(response)

        await asyncio.sleep(1)

        response = ""

        if self.task in ("all", "bets"):
            if not self.loud:
                self.channels_to_write[self.guild_to_use] = MockChannel()

            response, max_tokens_id, new_max_tokens_id = self.resolve_bets(
                filtered, intfar, intfar_reason, doinks, self.guild_to_use
            )
            if max_tokens_id != new_max_tokens_id:
                await self.assign_top_tokens_role(max_tokens_id, new_max_tokens_id)

        if self.task in ("all", "stats"):
            best_records, worst_records = self.save_stats(
                filtered, intfar, intfar_reason, doinks, self.guild_to_use
            )

            if best_records != [] or worst_records != []:
                records_response = self.get_beaten_records_msg(
                    best_records, worst_records, self.guild_to_use
                )
                response = records_response + response

        if self.loud and self.task == "all":
            await self.channels_to_write[self.guild_to_use].send(response)

        if self.play_sound:
            await self.play_event_sounds(self.guild_to_use, intfar, doinks)

        if self.ai_model is not None and self.task in ("all", "train"):
            self.config.log("Training AI Model with new game data.")
            train_data = shape_predict_data(
                self.database, self.riot_api, self.config, users_in_game
            )
            loss = train_online(
                self.ai_model, train_data, filtered[0][1]["gameWon"]
            )
            self.ai_model.save()
            self.config.log(f"Loss: {loss}")

        if self.config.generate_predictions_img:
            predictions_img = None
            for user_data in users_in_game:
                if ADMIN_DISC_ID == user_data[0]:
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
parser.add_argument("task", type=str, choices=("all", "bets", "stats", "train"))
parser.add_argument("-s", "--silent", action="store_true")
parser.add_argument("-p", "--play", action="store_true")

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
audio_client = AudioHandler(conf)
shop_client = ShopHandler(conf, database_client)
ai_model = Model(conf)
ai_model.load()

client = TestMock(args, conf, database_client, bet_client, riot_api, audio_client, shop_client, ai_model=ai_model)

client.run(conf.discord_token)
