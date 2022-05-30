from datetime import datetime
import json

class Config:
    def __init__(self):
        auth = json.load(open("resources/auth.json"))

        # ===== Meta and Auth =====
        self.use_dev_token = False
        self.debug = True
        self.testing = False
        self.discord_token = auth["discordToken"]
        self.riot_key = auth["riotDevKey"] if self.use_dev_token else auth["riotAPIKey"]
        self.env = auth["env"]
        self.database = "resources/database.db"
        self.generate_predictions_img = False
        self.min_game_minutes = 5 # Minimum amount of minutes for a game to be valid.

        # ===== Active Game Monitoring =====
        self.status_interval_dormant = 60 * 2 # Seconds to wait between checking for game status.
        self.status_interval_ingame = 30 # Seconds to wait between checking for status when in-game.

        # ===== Betting =====
        self.betting_tokens = "*good-boi points*"
        self.betting_tokens_for_win = 8
        self.betting_tokens_for_loss = 3
        self.betting_tokens_for_doinks = 15
        self.clash_multiplier = 5

        # ===== Shop =====
        self.max_shop_price = int(1e12)
        self.max_shop_quantity = 1000
        self.shop_open = False

        # ===== Intfar Criterias =====
        self.kda_lower_threshold = 1.3
        self.kda_death_criteria = 2
        self.death_lower_threshold = 9
        self.death_kda_criteria = 2.1
        self.kp_lower_threshold = 20
        self.kp_takedowns_criteria = 10
        self.kp_structures_criteria = 2
        self.kp_deaths_criteria = 2
        self.vision_score_lower_threshold = 11
        self.vision_kda_criteria = 3.0
        self.vision_secs_lower_threshold = 1200

        # ===== Honorable Mentions Criterias =====
        self.mentions_vision_wards = 0
        self.mentions_max_damage = 8000
        self.mentions_max_cs_per_min = 5.0
        self.mentions_epic_monsters = 0

        # ===== Noteworthy End-of-game Stats Criterias =====
        self.stats_min_time_dead = 60 * 10
        self.stats_min_objectives_stolen = 1
        self.stats_min_turrets_killed = 7

        # ===== Noteworthy Timeline-related Stats Criterias =====
        self.timeline_min_deficit = 8000
        self.timeline_min_lead = 8000
        self.timeline_min_curr_gold = 4000

        # ===== Int-Far of the Month =====
        self.ifotm_min_games = 10
        self.hour_of_ifotm_announce = 11 # Hour of the day on which to announce IFOTM.

        # ===== Logging & Messaging =====
        self.log_warning = 1
        self.log_error = 2
        self.message_timeout = 1.5

        # ===== ML Classifier =====
        self.ai_input_dim = (25, 170)
        self.ai_conv_filters = 128
        self.ai_conv_kernel = 2
        self.ai_conv_stride = 2
        self.ai_hidden_dim = 256
        self.ai_output_dim = 1
        self.ai_dropout = 0.3
        self.ai_validation_split = 0.75
        self.ai_batch_size = 32
        self.ai_learning_rate = 0.001
        self.ai_weight_decay = 0e-4
        self.ai_epochs = 100
        self.ai_init_range = 0.001

    def log(self, data, severity=0, end="\n"):
        curr_time = datetime.now()
        prefix = curr_time.strftime("%Y-%m-%d %H:%M:%S")
        if severity == self.log_warning:
            prefix = prefix + " - [Warning]"
        elif severity == self.log_error:
            prefix = prefix + " - [### ERROR ###]"

        if self.debug:
            print(prefix + " - " + str(data), flush=True, end=end)
