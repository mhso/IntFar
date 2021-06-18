import json

from test.runner import TestRunner, test
from api.config import Config
from api import award_qualifiers, game_stats

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        self.before_all(conf)

    @test
    def test_intfar_stuff(self, config):
        with open("stuff.json", encoding="utf-8") as fp:
            data = json.load(fp)

        users_in_game = [
            (115142485579137029, 'Prince Jarvan lV', 'a8acI9mAGm3mxTNPEqJPZmQ9LYkPnL5BNYG_tRWVMv_u-5E'),
            (172757468814770176, 'Stirred Martini', 'JaCbP2pIag8CVn3ERfvVP7QS6-OjNA-LInKW3gMkTytMO0Q'),
            (219497453374668815, 'Zapiens', 'uXbAPtnVfu7PNiOc_U_Z9jU5S1DPGee9YpJKWRjFNalqfLs'),
            (267401734513491969, 'Senile Felines', 'LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0'),
            (331082926475182081, 'Dumbledonger', 'z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o')
        ]

        filtered_data, users_in_game = game_stats.get_filtered_stats(users_in_game, users_in_game, data)

        (final_intfar,
         final_intfar_data,
         ties, ties_msg) = award_qualifiers.get_intfar(filtered_data, config)
