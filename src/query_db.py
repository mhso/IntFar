from argparse import ArgumentParser

from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_databases import get_database_client
from intfar.api.util import SUPPORTED_GAMES

from mhooge_flask.query_db import query_or_repl

parser = ArgumentParser()

parser.add_argument("-db", "--database", default="meta", type=str)
parser.add_argument("--query", default=None, type=str, nargs="+")
parser.add_argument("--raw", action="store_true")
parser.add_argument("--print", action="store_true")

args = parser.parse_args()

config = Config()

if args.database == "meta":
    database = MetaDatabase(config)
elif args.database in SUPPORTED_GAMES:
    database = get_database_client(args.database, config)
else:
    print("Database does not seem to exist. Exiting...")
    exit(0)

query_or_repl(database, args.query, args.raw, args.print)
