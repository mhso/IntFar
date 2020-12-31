from api.database import Database
from api.config import Config

conf = Config()

database_client = Database(conf)

print(database_client.get_all_bets()[347489125877809155])
