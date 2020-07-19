from datetime import datetime, timezone, tzinfo, timedelta
import asyncio
import config
import database

class TimeZone(tzinfo):
    def tzname(self, dt):
        return "Europe/Copenhagen"

    def utcoffset(self, dt):
        return self.dst(dt) + timedelta(0, 0, 0, 0, 0, 1, 0)

    def dst(self, dt):
        if dt.month < 10 or dt.month > 3:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        if dt.month == 10 and dt.day < 25:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        if dt.month == 3 and dt.day > 28:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        return timedelta(0, 0, 0, 0, 0, 1, 0)

class MonthlyIntfar:
    def __init__(self):
        self.cph_timezone = TimeZone()
        current_time = datetime.now(self.cph_timezone)
        current_month = current_time.month
        next_month = 1 if current_month == 12 else current_month + 1
        self.time_at_announcement = current_time.replace(current_time.year, next_month,
                                                         1, 12, 0, 0, 0, self.cph_timezone)
        print("Starting Int-Far-of-the-month monitor... Monthly Int-Far will be crowned at ", end="")
        print(self.time_at_announcement.strftime("%Y-%m-%d %H:%M:%S"))

    def get_seconds_left(self):
        return (self.time_at_announcement - datetime.now(self.cph_timezone)).seconds

    def get_description(self, intfar_details):
        nickname_1st = intfar_details[0][1]
        count_1st = intfar_details[0][0]
        nickname_2nd = intfar_details[1][1]
        count_2nd = intfar_details[1][0]
        nickname_3rd = intfar_details[2][1]
        count_3rd = intfar_details[2][0]
        winner_str = ""
        desc_str = ""
        tie_count = 0
        if count_1st == count_2nd == count_3rd:
            tie_count = 3
        elif count_1st == count_2nd:
            tie_count = 2
        if tie_count == 0:
            winner_str = f"{nickname_1st}!!! "
            desc_str = f"He has \"won\" a total of **{count_1st}** Int-Far awards this month!!!\n"
            runner_up_str = "Runner up goes to "
            if count_2nd == count_3rd:
                runner_up_str += f"both {nickname_2nd} and {nickname_3rd} "
                runner_up_str += f"for a tied **{count_2nd}** Int-Far awards!\n"
            else:
                runner_up_str += f"{nickname_2nd} for being almost as bad with "
                runner_up_str += f"**{count_2nd}** Int-Far awards!\n"
                runner_up_str += f"Finally, {nickname_3rd} gets a bronze medal for "
                runner_up_str += f"a bad-but-no-as-terrible {count_3rd} Int-Far awards!\n"
            desc_str += runner_up_str
        if tie_count == 2:
            winner_str += f"{nickname_1st} **AND** {nickname_2nd}!!! "
            desc_str = f"They are both equally terrible with a tied **{count_1st}** "
            desc_str += "Int-Far awards this month!!!\n"
            desc_str += f"Second place goes to {nickname_3rd} with **{count_3rd}** Int-Far awards!\n"
        if tie_count == 3:
            winner_str += f"{nickname_1st}, {nickname_2nd} **AND** {nickname_3rd}!!! "
            desc_str = f"They are ALL equally terrible with a tied **{count_1st}** "
            desc_str += "Int-Far awards this month!!!\n"

        desc_str += "GIVE THEM A ROUND OF APPLAUSE, LADIES AND GENTLEMEN!!\n"
        return winner_str + desc_str

if __name__ == "__main__":
    monthly_monitor = MonthlyIntfar()
    conf = config.Config()
    db_client = database.Database(conf)
    details = db_client.get_intfars_of_the_month()
    print(details)
