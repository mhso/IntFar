from datetime import datetime
from intfar.api import config, meta_database
from intfar.api.util import MONTH_NAMES

class MonthlyIntfar:
    """
    Class for handling the tracking of when to announce Int-Far of the month.
    """

    def __init__(self, hour_of_announce):
        current_time = datetime.now()
        current_month = current_time.month
        next_month = 1 if current_month == 12 else current_month + 1
        next_year = current_time.year if next_month != 1 else current_time.year + 1

        # If today is the first day of the month and the time if before 14:00,
        # we should announce the Int-Far at the current month (and year).
        # Otherwise, we should announce it at the first day of the next month.
        month_to_announce = (
            current_month
            if current_time.day == 1 and current_time.hour < hour_of_announce
            else next_month
        )
        year_to_announce = current_time.year if month_to_announce == current_month else next_year
        self.time_at_announcement = current_time.replace(
            year_to_announce, month_to_announce, 1, hour_of_announce, 0, 0, 0
        )

    def should_announce(self):
        """
        Get seconds left until announcement time (first of the month at 12:00).
        """
        return self.time_at_announcement < datetime.now()

    def get_pct_desc(self, games, intfars, pct):
        return f"**{pct:.2f}%** ({intfars}/{games})"

    def get_description_and_winners(self, intfar_details):
        nickname_1st = intfar_details[0][0]
        games_1st = intfar_details[0][1]
        intfars_1st = intfar_details[0][2]
        pct_1st = intfar_details[0][3]
        pct_desc_1st = self.get_pct_desc(games_1st, intfars_1st, pct_1st)

        if len(intfar_details) > 1:
            nickname_2nd = intfar_details[1][0]
            games_2nd = intfar_details[1][1]
            intfars_2nd = intfar_details[1][2]
            pct_2nd = intfar_details[1][3]
            pct_desc_2nd = self.get_pct_desc(games_2nd, intfars_2nd, pct_2nd)
        else:
            nickname_2nd, games_2nd, intfars_2nd, pct_2nd, pct_desc_2nd = None, None, None, None, None

        if len(intfar_details) > 2:
            nickname_3rd = intfar_details[2][0]
            games_3rd = intfar_details[2][1]
            intfars_3rd = intfar_details[2][2]
            pct_3rd = intfar_details[2][3]
            pct_desc_3rd = self.get_pct_desc(games_3rd, intfars_3rd, pct_3rd)
        else:
            nickname_3rd, games_3rd, intfars_3rd, pct_3rd, pct_desc_3rd = None, None, None, None, None

        winners = 1

        winner_str = ""
        desc_str = ""
        tie_count = 0
        if pct_1st == pct_2nd == pct_3rd and intfars_1st == intfars_2nd == intfars_3rd:
            tie_count = 3

        elif pct_1st == pct_2nd and intfars_1st == intfars_2nd:
            tie_count = 2

        if tie_count == 0: # Int-Far #1 and Int-Far #2 values are distinct.
            winner_str = f"--- {nickname_1st}!!! ---\n"
            desc_str = f"He has inted in {pct_desc_1st} of his games this month!!!\n"
            desc_str += "You deserve this: :first_place: \n"
            desc_str += "You will also receive a badge of shame on Discord {emote_main}\n"

            if len(intfar_details) > 1:
                runner_up_str = "\nRunner up goes to "

                if pct_2nd == pct_3rd and intfars_2nd == intfars_3rd: # Int-Far #2 and Int-Far #3 values are equal.
                    runner_up_str += f"both {nickname_2nd} and {nickname_3rd} "
                    runner_up_str += f"for a tied {pct_desc_2nd} of games where they were Int-Far!\n"
                    runner_up_str += "You both get one of these: :second_place: :second_place: \n"

                else: # All three Int-Far values are distinct.
                    runner_up_str += f"{nickname_2nd} for being almost as bad with "
                    runner_up_str += f"{pct_desc_2nd} of games being Int-Far!\n"
                    runner_up_str += "Take this medal for your troubles: :second_place: \n"

                    if len(intfar_details) > 2:
                        runner_up_str += f"\nFinally, {nickname_3rd} gets a :third_place: for "
                        runner_up_str += f"a bad-but-not-as-terrible {pct_desc_3rd} of inted games! \n"

                desc_str += runner_up_str

        if tie_count == 2: # Int-Far #1 and Int-Far #2 values are equal.
            winner_str += f"--- {nickname_1st} **AND** {nickname_2nd}!!! ---\n"
            desc_str = f"They are both equally terrible with a tied {pct_desc_1st} "
            desc_str += "of games were they were Int-Far this month!!!\n"
            desc_str += "You both deserve this: :first_place: :first_place: \n"
            desc_str += "You will also both receive a badge of shame on Discord {emote_main}\n"

            if len(intfar_details) > 2:
                desc_str += f"\nSecond place goes to {nickname_3rd} for inting in {pct_desc_3rd} "
                desc_str += "of his games! Take this, my boi: :second_place: \n"

            winners = 2

        if tie_count == 3: # Int-Far values for all three 'winners' are equal.
            winner_str += f"--- {nickname_1st}, {nickname_2nd} **AND** {nickname_3rd}!!! ---\n"
            desc_str = f"They are ALL equally terrible with a tied {pct_desc_1st} "
            desc_str += "of games in which they were Int-Far this month!!!\n"
            desc_str += "You all deserve this: :first_place: :first_place: :first_place: \n"
            desc_str += "You will also all receive a badge of shame on Discord {emote_main}\n"
            winners = 3

        desc_str += "\nGIVE THEM A ROUND OF APPLAUSE, LADIES AND GENTLEMEN!!!!!!\n"
        return winner_str + desc_str, winners

if __name__ == "__main__":
    conf = config.Config()
    monthly_monitor = MonthlyIntfar(conf.hour_of_ifotm_announce)
    db_client = meta_database.Database(conf)
    details = db_client.get_intfars_of_the_month()
    # details = [
    #     (1, 40, 12, 30),
    #     (2, 20, 6, 30),
    #     (3, 20, 6, 20),
    # ]
    intfar_details = [
        ("Disc ID: " + str(disc_id), games, intfars, ratio)
        for (disc_id, games, intfars, ratio) in details
    ]

    month = monthly_monitor.time_at_announcement.month
    prev_month = month - 1 if month != 1 else 12
    month_name = MONTH_NAMES[prev_month-1]

    intro_desc = f"THE RESULTS ARE IN!!! Int-Far of the month for {month_name} is...\n\n"
    intro_desc += "*DRUM ROLL*\n\n"
    desc, num_winners = monthly_monitor.get_description_and_winners(intfar_details)
    winners = [tupl[0] for tupl in details[:num_winners]]
    desc += ":clap: :clap: :clap: :clap: :clap: \n"
    desc += "{emote_uwu} {emote_sadbuttrue} {emote_smol_dave} "
    desc += "{emote_extra_creme} {emote_happy_nono} {emote_hairy_retard}"
    print(intro_desc + desc)
