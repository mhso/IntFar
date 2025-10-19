import os
from src.api.util import SUPPORTED_GAMES
from src.api.config import Config
from src.api.game_databases import get_database_client
from src.api.meta_database import MetaDatabase
from src.api.util import SUPPORTED_GAMES

class BaseTestExecutor:
    def __enter__(self):
        self.config = Config()
        self.config.static_folder = f"{self.config.src_folder}/app/static"
        self.config.database_folder += "/test"

        self._remove_databases()

        self.meta_database = MetaDatabase(self.config)
        self.game_databases = {
            game: get_database_client(game, self.config)
            for game in SUPPORTED_GAMES
        }

        self._add_test_users()

        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._remove_databases()

    def _remove_databases(self):
        meta_database_path = f"{self.config.database_folder}/meta.db"
        if os.path.exists(meta_database_path):
            os.remove(meta_database_path)

        for game in SUPPORTED_GAMES:
            game_database_path = f"{self.config.database_folder}/{game}.db"
            if os.path.exists(game_database_path):
                os.remove(game_database_path)

    def _add_test_users(self):
        test_users = {
            "lol": [
                (115142485579137029, "SIugger", "a8acI9mAGm3mxTNPEqJPZmQ9LYkPnL5BNYG_tRWVMv_u-5E", "dobVtKS51pSWF51ci-Mjm3By0U1vw0IbdsdUmSUCLjFF1u4dPrTS3hokFg6fvEublovdu1SmFc0QXQ"),
                (172757468814770176, "Glubstein", "JaCbP2pIag8CVn3ERfvVP7QS6-OjNA-LInKW3gMkTytMO0Q", "oSbXCkIVbiBNKJP--H6gh5U9iUbvW6KtEvebaSi2PxpH29lgYCgOADHdsNyqfIkctckbm5oyao0FEg"),
                (267401734513491969, "Senile Felines", "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0", "Vg03sswLbwPm1yaJp8ACbObNUCkfJazuq_afJnHrfxZYYy-GvKIipeazQxIjrbqnoNkJFISDuuw9sg"),
                (347489125877809155, "Nønø", "vWqeigv3NlpebAwh309gZ8zWul9rNIv6zUKXGFeRWqih9ko", "1_70uHLfugLXirzVmbJCm9uHePRl34sqaO0wHU5tCdPvwtU6NfGzNb-8L8Z-mD3eoZ9FReAO9qkkcQ"),
                (331082926475182081, "Eddïe Smurphy", "z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o", "VNoVyAA9kI61EGZKkWqMOOZfc2e0YVuo-YDiipFSgs5-Bt5DU4x2o81kF45cnNXC2uIwsiy20qKxig"),
            ]
        }
        
        for game in test_users:
            for disc_id, name, summoner_id, puuid in test_users[game]:
                self.meta_database.add_user(disc_id)
                self.game_databases[game].add_user(
                    disc_id,
                    player_name=name,
                    player_id=summoner_id,
                    puuid=puuid
                )
