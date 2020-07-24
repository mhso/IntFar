from datetime import datetime
import config
import database

database = database.Database(config.Config())

(games, earliest_game, users,
 intfars, twos, threes, fours, fives) = database.get_meta_stats()

response = ""
earliest_time = datetime.fromtimestamp(earliest_game).strftime("%Y-%m-%d")
response += f"Since {earliest_time}:\n"
response += f"- **{games}** games have been played\n"
response += f"- **{users}** users have signed up\n"
response += f"- **{intfars}** Int-Far awards have been given\n"
response += "Of all games played:\n"
response += f"- **{twos}%** were as a duo\n"
response += f"- **{threes}%** were as a three-man\n"
response += f"- **{fours}%** were as a four-man\n"
response += f"- **{fives}%** were as a five-man stack"
print(response)
