from datetime import datetime

class Config:
    def __init__(self):
        # ===== Meta and Auth =====
        self.use_dev_token = False
        self.debug = True
        self.testing = False
        self.discord_token = ""
        self.env = ""
        self.riot_key = ""
        self.database = "resources/database.db"
        self.generate_predictions_img = False
        self.min_game_minutes = 5 # Minimum amount of minutes for a game to be valid.

        # ===== Active Game Monitoring =====
        self.status_interval_dormant = 60 * 2 # 2 minutes wait time between checking for status.
        self.status_interval_ingame = 30 # 30 seconds wait time when in-game.

        # ===== Betting =====
        self.betting_tokens = "*good-boi points*"
        self.betting_tokens_for_win = 8
        self.betting_tokens_for_loss = 3
        self.betting_tokens_for_doinks = 15
        self.clash_multiplier = 5

        # ===== Shop =====
        self.max_shop_price = int(1e12)
        self.max_shop_quantity = 1000
        self.shop_open = True

        # ===== Intfar Criterias =====
        self.kda_lower_threshold = 1.3
        self.kda_death_criteria = 2
        self.death_lower_threshold = 9
        self.death_kda_criteria = 2.1
        self.kp_lower_threshold = 20
        self.kp_takedowns_criteria = 10
        self.kp_structures_criteria = 2
        self.vision_score_lower_threshold = 11
        self.vision_kda_criteria = 3.0
        self.vision_secs_lower_threshold = 1200

        # ===== Int-Far of the Month =====
        self.ifotm_min_games = 10
        self.hour_of_ifotm_announce = 12 # Hour of the day on which to announce IFOTM.

        # ===== Noteworthy end-of-game stats =====
        self.stats_min_cc = 60

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
