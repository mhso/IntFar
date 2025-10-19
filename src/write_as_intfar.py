import argparse
import sys
import io

from api.betting import BettingHandler
from api.config import Config
from api.meta_database import Database
from api.bets import get_betting_handler
from discbot.discord_bot import DiscordClient
from api.util import GUILD_MAP, SUPPORTED_GAMES

CHANNEL_MAP = {
    "nibs": 730744358751567902,
    "circus": 805218121610166272,
    "core": 808796236692848650,
    "test": 512363920044982274
}

async def write_message(client, message, channel_id):
    channel = client.get_channel(channel_id)
    try:
        needle = "[mention:"
        mention_index = message.index(needle)
        after_mention_index = message[mention_index + len(needle):]
        end_index = after_mention_index.index("]")
        disc_id = message[mention_index + len(needle):mention_index + len(needle) + end_index]
        mention_str = discord_client.get_mention_str(int(disc_id), GUILD_MAP[args.guild])

        message = message.replace(f"{needle}{disc_id}]", mention_str)

    except ValueError:
        pass

    await channel.send(client.insert_emotes(message))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("guild", choices=CHANNEL_MAP)

    args = parser.parse_args()

    input_stream = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    lines = input_stream.readlines()

    if lines == []:
        print("Error: No message provided (should be input to stdin)")
        exit(0)

    conf = Config()
    database_client = Database(conf)
    bet_client = BettingHandler(conf, database_client)
    betting_handlers = {game: get_betting_handler(game, conf, database_client) for game in SUPPORTED_GAMES}

    discord_client = DiscordClient(conf, database_client, bet_client)

    channel_id = CHANNEL_MAP[args.guild]
    message = "".join(lines)

    GUILD_MAP["test"] = 512363920044982272

    discord_client.add_event_listener("ready", write_message, discord_client, message, channel_id)

    discord_client.run(conf.discord_token)
