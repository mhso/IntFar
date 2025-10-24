import json
import random
from datetime import datetime

from test.runner import TestRunner, test
from intfar.api.config import Config
from intfar.api.meta_database import Database
from intfar.api import award_qualifiers, game_stats
from intfar.discbot.discord_bot import get_cool_stat_flavor_text, get_doinks_flavor_text, get_intfar_flavor_text, get_reason_flavor_text

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        db = Database(conf)
        self.before_all(config=conf, database=db)

    @test
    def test_intfar_stuff(self):
        with open("stuff.json", encoding="utf-8") as fp:
            data = json.load(fp)

        users_in_game = [
            (115142485579137029, 'Prince Jarvan lV', 'a8acI9mAGm3mxTNPEqJPZmQ9LYkPnL5BNYG_tRWVMv_u-5E'),
            (172757468814770176, 'Stirred Martini', 'JaCbP2pIag8CVn3ERfvVP7QS6-OjNA-LInKW3gMkTytMO0Q'),
            (219497453374668815, 'Zapiens', 'uXbAPtnVfu7PNiOc_U_Z9jU5S1DPGee9YpJKWRjFNalqfLs'),
            (267401734513491969, 'Senile Felines', 'LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0'),
            (331082926475182081, 'Dumbledonger', 'z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o')
        ]

        relevant_data, users_in_game = game_stats.get_relevant_stats(users_in_game, users_in_game, data)

        (final_intfar,
         final_intfar_data,
         ties, ties_msg) = award_qualifiers.get_intfar(relevant_data, self.config)

    @test
    def test_flavor_texts(self):
        random.seed(42)
        flavor = get_cool_stat_flavor_text(1, 1)
        self.assert_equals(flavor, "went against ALL THE ODDS, stealing **1** jungle objective {emote_nazi}", "Cool Stats Steals 1")
        random.seed(42)
        flavor = get_cool_stat_flavor_text(1, 2)
        self.assert_equals(flavor, "went against ALL THE ODDS, stealing **2** jungle objectives {emote_nazi}", "Cool Stats Steals 2")

        random.seed(42)
        flavor = get_doinks_flavor_text(3, 1)
        self.assert_equals(flavor, "managing to last hit the entire enemy team in a single fight, getting **1** TASTY pentakill!", "Doinks Penta 1")
        random.seed(42)
        flavor = get_doinks_flavor_text(3, 2)
        self.assert_equals(flavor, "managing to last hit the entire enemy team in a single fight, getting **2** TASTY pentakills!", "Doinks Penta 2")

        reason = get_reason_flavor_text(0.3, "kda")
        flavor = get_intfar_flavor_text("Gual", reason)
        self.assert_equals(flavor, "And the Int-Far goes to... Gual {emote_hairy_retard} He wins for having a tragic KDA of **0.3**!", "Intfar KDA")

    @test
    def test_intfar_count(self):
        self.assert_no_exception(self.database.get_intfar_count, "Everyone All Time")
        self.assert_no_exception(lambda: self.database.get_intfar_count(267401734513491969), "Single All Time")
        timestamp = int(datetime(2021, 10, 1, 0, 0, 0).timestamp())
        self.assert_no_exception(
            lambda: self.database.get_intfar_count(time_after=timestamp),
            "Everyone After 2021/10/01"
        )

        self.assert_no_exception(
            lambda: self.database.get_intfar_count(267401734513491969, time_after=timestamp),
            "Single After 2021/10/01"
        )

        print(self.database.get_intfar_count(time_after=timestamp))
        print(self.database.get_intfar_count(267401734513491969, time_after=timestamp))
