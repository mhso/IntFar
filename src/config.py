from datetime import datetime

class Config:
    def __init__(self):
        self.use_dev_token = False
        self.debug = True
        self.testing = False
        self.discord_token = ""
        self.riot_key = ""
        self.status_interval_dormant = 60 * 2 # 2 minutes wait time between checking for status.
        self.status_interval_ingame = 30 # 30 seconds wait time when in-game.
        self.database = "database.db"
        self.betting_tokens = "*good-boi points*"
        self.betting_tokens_for_win = 8
        self.betting_tokens_for_loss = 3
        self.betting_tokens_for_doinks = 15
        self.kda_lower_threshold = 1.3
        self.kda_death_criteria = 2
        self.death_lower_threshold = 9
        self.death_kda_criteria = 2.1
        self.kp_lower_threshold = 20
        self.kp_takedowns_criteria = 10
        self.kp_structures_criteria = 3
        self.vision_score_lower_threshold = 11
        self.vision_kda_criteria = 3.0
        self.log_warning = 1
        self.log_error = 2
        self.message_timeout = 1.5
        self.ifotm_min_games = 5

    def log(self, data, severity=0, end="\n"):
        curr_time = datetime.now()
        prefix = curr_time.strftime("%Y-%m-%d %H:%M:%S")
        if severity == self.log_warning:
            prefix = prefix + " - [Warning]"
        elif severity == self.log_error:
            prefix = prefix + " - [ERROR]"

        if self.debug:
            print(prefix + " - " + str(data), flush=True, end=end)
