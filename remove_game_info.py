from sys import argv
from api.config import Config
from api.database import Database
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("game")
parser.add_argument("game_id")

args = parser.parse_args()

game = args.game
game_id = args.game_id

config = Config()

db_client = Database(config)

db_client.delete_game(game, game_id)

print(f"Deleted game data for game_id: {game_id}")
