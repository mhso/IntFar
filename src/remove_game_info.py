from sys import argv
from api.config import Config
from api.game_databases import get_database_client
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("game")
parser.add_argument("game_id")

args = parser.parse_args()

game = args.game
game_id = args.game_id

config = Config()

db_client = get_database_client(game, config)
db_client.delete_game(game_id)

print(f"Deleted game data for game_id: {game_id}")
