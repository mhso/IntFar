from sys import argv
from api.config import Config
from api.database import Database

if len(argv) < 2:
    exit(0)

game_id = int(argv[1])

config = Config()

db_client = Database(config)

db_client.delete_game(game_id)
print(f"Delete game with ID {game_id}")
