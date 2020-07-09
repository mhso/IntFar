from datetime import datetime

class Config:
    def __init__(self):
        self.use_dev_token = False
        self.debug = True
        self.discord_token = ""
        self.riot_key = ""
        self.status_interval = 60*10 # 10 minutes wait time between checking for status.
        self.database = "database.db"
        self.kda_lower_threshold = 1.5
        self.highest_death_threshold = 9
        self.log_warning = 1
        self.log_error = 2

    def log(self, data, severity=0):
        curr_time = datetime.now()
        prefix = curr_time.strftime("%Y-%m-%d %H:%M:%S")
        if severity == self.log_warning:
            prefix = prefix + " - [Warning]"
        elif severity == self.log_error:
            prefix = " - [ERROR]"

        if self.debug:
            print(prefix + " - " + str(data), flush=True)
