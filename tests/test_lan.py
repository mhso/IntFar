import json
from unittest import TestCase
from tests.synthetic_data.spec import DataSpec
from tests.synthetic_data.raw_data import create_synthetic_data

from tests.base_test_executor import BaseTestExecutor
from src.api.util import GUILD_MAP
from src.api.game_apis import get_api_client
from src.api.game_monitor import GameMonitor
from src.api.game_monitors import get_game_monitor
from src.api import lan

TEST_ID = 5452408885

class TestWrapper(TestCase):
    def test_tilt_value(self):
        recent_games = [1, 1, -1, 1, -1, 1, -1, 1, -1]
        tilt_value = lan.get_tilt_value(recent_games)[0]
        print(tilt_value)

    def _update_and_validate_bingo(
        self,
        game_monitor,
        game_database,
        raw_game_data,
        challenge_id,
        expected_progress,
        expected_completed,
        expected_completed_by,
        tabula_rasa=True
    ):
        post_game_data = game_monitor.handle_game_over(
            raw_game_data,
            GameMonitor.POSTGAME_STATUS_OK,
            GUILD_MAP["core"]
        )

        if tabula_rasa:
            for challenge in lan.get_current_bingo_challenges(game_database):
                self.assertEqual(challenge["progress"], 0)
                self.assertEqual(challenge["new_progress"], False)
                self.assertEqual(challenge["completed"], False)
                self.assertEqual(challenge["completed_by"], None)
                self.assertEqual(challenge["notification_sent"], False)

        lan.update_bingo_progress(game_database, post_game_data)

        bingo_challenges = {
            challenge["id"]: challenge
            for challenge
            in lan.get_current_bingo_challenges(game_database)
        }

        # Validate data after updating bingo progress
        self.assertEqual(bingo_challenges[challenge_id]["progress"], expected_progress)
        self.assertEqual(bingo_challenges[challenge_id]["new_progress"], 1 if expected_progress > 0 else 0)
        self.assertEqual(bingo_challenges[challenge_id]["completed"], expected_completed)
        self.assertEqual(bingo_challenges[challenge_id]["completed_by"], expected_completed_by)

    def test_bingo_big_lead(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "teams.0.win": DataSpec(True),
                    "teams.1.win": DataSpec(False),
                    "timeline.frames.-1.participantFrames.1-6.totalGold": DataSpec(14000),
                    "timeline.frames.-1.participantFrames.6-11.totalGold": DataSpec(5000),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "big_lead",
                1,
                True,
                None
            )

    def test_bingo_bounty_gold(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.0-5.challenges.bountyGold": DataSpec(500),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "bounty_gold",
                2500,
                False,
                None
            )

    def test_bingo_buff_steals(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.0-4.challenges.buffsStolen": DataSpec(2),
                    "participants.4.challenges.buffsStolen": DataSpec(3),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "buff_steals",
                10,
                True,
                None
            )

    def test_bingo_damage_dealt(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.*.totalDamageDealtToChampions": DataSpec(100000),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "damage_dealt",
                500000,
                False,
                None
            )

    def test_bingo_dives(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.*.kills": DataSpec(5),
                    "participants.0-5.challenges.killsNearEnemyTurret": DataSpec(1),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "dives",
                5,
                True,
                None
            )

    def test_bingo_doinks(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.*.kills": DataSpec(5),
                    "participants.*.assists": DataSpec(1, 10),
                    "participants.*.deaths": DataSpec(2, 10),
                    "participants.0-2.neutralMinionsKilled": DataSpec(90),
                    "participants.0-2.totalMinionsKilled": DataSpec(90),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "doinks",
                2,
                False,
                None
            )

    def test_bingo_dragon_souls(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"timeline.frames.15.events.0": DataSpec({"type": "DRAGON_SOUL_GIVEN", "teamId": 100})}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "dragon_souls",
                1,
                False,
                None
            )
    
    def test_bingo_early_baron(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "timeline.frames.21.events.0": DataSpec(
                        {
                            "type": "ELITE_MONSTER_KILL",
                            "monsterType": "BARON_NASHOR",
                            "teamId": 100,
                            "timestamp": 1230
                        }
                    )
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "early_baron",
                1,
                True,
                None
            )

    def test_bingo_elder_dragon(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "timeline.frames.21.events.0": DataSpec(
                        {
                            "type": "ELITE_MONSTER_KILL",
                            "monsterType": "ELDER_DRAGON",
                            "teamId": 100
                        }
                    )
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "elder_dragon",
                1,
                True,
                None
            )

    def test_bingo_fast_win(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "teams.0.win": DataSpec(True),
                    "teams.1.win": DataSpec(False),
                    "gameDuration": DataSpec(1140)
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "fast_win",
                1,
                True,
                None
            )

    def test_bingo_flawless_ace(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.flawlessAces": DataSpec(1)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "flawless_ace",
                1,
                True,
                None
            )

    def test_bingo_fountain_kill(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.1.challenges.takedownsInEnemyFountain": DataSpec(1)}
            )

            second_player = None
            for disc_id in context.game_databases["lol"].game_users.keys():
                if raw_game_data["participants"][1]["summonerId"] in context.game_databases["lol"].game_users[disc_id].player_id:
                    second_player = disc_id
                    break

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "fountain_kill",
                1,
                True,
                second_player
            )

    def test_bingo_jungle_doinks(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "teams.0.objectives.baron.kills": DataSpec(1),
                    "teams.0.objectives.dragon.kills": DataSpec(4)
                }
            )

            jungle_player = None
            for participant_data in raw_game_data["participants"]:
                if participant_data["teamPosition"] == "JUNGLE":
                    for disc_id in context.game_databases["lol"].game_users.keys():
                        if participant_data["summonerId"] in context.game_databases["lol"].game_users[disc_id].player_id:
                            jungle_player = disc_id
                            break

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "jungle_doinks",
                1,
                True,
                jungle_player
            )

    def test_bingo_killing_sprees(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.killingSprees": DataSpec(32)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "killing_sprees",
                10,
                True,
                None
            )

    def test_bingo_kills(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "participants.*.kills": DataSpec(5),
                    "participants.*.assists": DataSpec(1, 10),
                    "participants.*.deaths": DataSpec(2, 10),
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "kills",
                25,
                False,
                None
            )

    def test_bingo_outnumbered_kills(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.outnumberedKills": DataSpec(1)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "outnumbered_kills",
                5,
                True,
                None
            )

    def test_bingo_pentakill(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0.pentaKills": DataSpec(1)}
            )

            first_player = None
            for disc_id in context.game_databases["lol"].game_users.keys():
                if raw_game_data["participants"][0]["summonerId"] in context.game_databases["lol"].game_users[disc_id].player_id:
                    first_player = disc_id
                    break

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "pentakill",
                1,
                True,
                first_player
            )

    def test_bingo_solo_kills(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.soloKills": DataSpec(2)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "solo_kills",
                10,
                True,
                None
            )

    def test_bingo_spells_casted(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.abilityUses": DataSpec(1000)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "spells_casted",
                5000,
                True,
                None
            )

    def test_bingo_spells_dodged(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.skillshotsDodged": DataSpec(50)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "spells_dodged",
                200,
                True,
                None
            )

    def test_bingo_spells_hit(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-5.challenges.skillshotsHit": DataSpec(100)}
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "spells_hit",
                500,
                True,
                None
            )

    def test_bingo_steals(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {"participants.0-2.objectivesStolen": DataSpec(1)}
            )

            second_player = None
            for disc_id in context.game_databases["lol"].game_users.keys():
                if raw_game_data["participants"][1]["summonerId"] in context.game_databases["lol"].game_users[disc_id].player_id:
                    second_player = disc_id
                    break

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "steals",
                2,
                True,
                second_player
            )

    def test_bingo_two_barons(self):
        with BingoTestExecutor() as context:
            raw_game_data = create_synthetic_data(
                "lol",
                context.game_databases,
                {
                    "teams.0.objectives.baron.kills": DataSpec(2)
                }
            )

            self._update_and_validate_bingo(
                context.game_monitor,
                context.game_databases["lol"],
                raw_game_data,
                "two_barons",
                1,
                True,
                None
            )

    def test_bingo_wins(self):
        with BingoTestExecutor() as context:
            for i in range(5):
                raw_game_data = create_synthetic_data(
                    "lol",
                    context.game_databases,
                    {
                        "teams.0.win": DataSpec(True),
                        "teams.1.win": DataSpec(False)
                    }
                )

                self._update_and_validate_bingo(
                    context.game_monitor,
                    context.game_databases["lol"],
                    raw_game_data,
                    "wins",
                    i + 1,
                    i == 4,
                    None,
                    i == 0 
                )


class BingoTestExecutor(BaseTestExecutor):
    def __init__(self):
        super().__init__()
        self.game_monitor = None

    def __enter__(self):
        super().__enter__()

        api_client = get_api_client("lol", self.config)
        self.game_monitor = get_game_monitor(
            "lol",
            self.config,
            self.meta_database,
            self.game_databases["lol"],
            api_client
        )

        lan.insert_bingo_challenges(self.game_databases["lol"])

        return self
