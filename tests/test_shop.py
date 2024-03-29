from test.runner import TestRunner, test
from api.meta_database import Database
from api.config import Config
from api.shop import ShopHandler

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        conf.database = "test.db"
        database_client = Database(conf)
        shop_handler = ShopHandler(conf, database_client)
        self.before_all(shop_handler, database_client)

    def before_test(self):
        self.test_args[1].reset_shop()


