class Config:
    def __init__(self):
        self.use_dev_token = False
        self.debug = True
        self.discord_token = ""
        self.riot_key = ""
        self.status_interval = 60*10 # 10 minutes wait time between checking for status.
        self.database = "database.db"
        self.kda_lower_threshold = 1.0

    def log(self, data):
        if self.debug:
            print("DEBUG: " + str(data), flush=True)
