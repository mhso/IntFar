import json

class Config:
    def __init__(self):
        # ===== File paths =====
        file_split = __file__.replace("\\", "/").split("/")
        self.src_folder = "/".join(file_split[:-2])
        self.resources_folder = "/".join(file_split[:-3]) + "/resources"

        auth = json.load(open(f"{self.resources_folder}/auth.json"))

        # ===== Meta and Auth =====
        self.use_dev_token = False
        self.debug = True
        self.testing = False
        self.discord_token = auth["discordToken"]
        self.riot_key = auth["riotDevKey"] if self.use_dev_token else auth["riotAPIKey"]
        self.youtube_key = auth["youtubeAPIKey"]
        self.jeopardy_cheetsheet_pass = auth["jeopardyCheatsheetPassword"]
        self.steam_2fa_code = None
        self.steam_key = auth["steamAPIKey"]
        self.steam_secrets = auth["steamSecrets"]
        self.steam_username = auth["steamUsername"]
        self.steam_password = auth["steamPassword"]
        self.env = auth["env"]
        self.database_folder = f"{self.resources_folder}/databases"
        self.schema_folder = f"{self.resources_folder}/schemas"
        self.generate_predictions_img = False
        self.performance_mimimum_games = 10

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

        # ===== Honorable Mentions Criterias =====
        self.mentions_vision_wards = 0
        self.mentions_max_damage = 8000
        self.mentions_max_cs_per_min = 5.0
        self.mentions_epic_monsters = 0

        # ===== Noteworthy End-of-game Stats Criterias =====
        self.stats_min_time_dead = 60 * 10
        self.stats_min_objectives_stolen = 1
        self.stats_min_turrets_killed = 7
        self.stats_min_win_loss_streak = 3

        # ===== Noteworthy Timeline-related Stats Criterias =====
        self.timeline_min_deficit = 8000
        self.timeline_min_lead = 8000
        self.timeline_min_curr_gold = 4000
        self.timeline_min_total_gold = 17000

        # ===== Int-Far of the Month =====
        self.ifotm_min_games = 10
        self.hour_of_ifotm_announce = 11 # Hour of the day on which to announce IFOTM.

        # ===== Logging & Messaging =====
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
