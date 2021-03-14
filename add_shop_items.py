import json
from api.database import Database
from api.config import Config

auth = json.load(open("discbot/auth.json"))

config = Config()

database = Database(config)

items = [
    ("Tesla Inc.", 589_711_600_000, 1),
    ("ISS", 150_000_000_000, 1),
    ("Saturn V Rocket", 35_800_000_000, 3),
    ("Al Marjan Island", 462_000_000, 1),
    ("Luxury Yacht", 201_782_515, 5),
    ("Castle", 71_832_300, 5),
    ("Private Jet", 64_649_070, 5),
    ("Bugatti Divo", 4_166_273, 10),
    ("Bugatti Chiron", 2_147_785, 15),
    ("Bitcoin", 42_948, 1000),
    ("Souvenir Dragon Lore", 26_574, 3),
    ("Romanée-Conti Wine", 14_107, 5),
    ("Geforce GTX 3090", 2298, 10),
    ("Macbook Air", 718, 20),
    ("Gamestop Stonks", 250, 1000),
    ("Premium Tendies", 7, 100),
    ("Tasty Tendies", 3, 1000),
    ("Dave's Dignity", 1, 1)
]

for item, price, quantity in items:
    copies = [(item, price) for _ in range(quantity)]
    database.add_items_to_shop(copies)
