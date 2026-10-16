import argparse
from datetime import datetime

import matplotlib.pyplot as plt

from intfar.api.game_database import GameDatabase
from intfar.api.game_databases import get_database_client
from intfar.api.config import Config
from intfar.api.util import SUPPORTED_GAMES

def bar_plot(title, games, wins, y_step, tick_labels, font_scale, y_text_offset):
    fig, ax = plt.subplots()

    width = 35
    height = width * 0.5625
    fig.set_size_inches(width, height, forward=True)

    max_count = max(games)
    count_cap = int(max_count + (5 - (5 * ((max_count % 5) / 5)))) if max_count % 5 else max_count

    x_values = [x for x in range(len(games))]
    minor_y_ticks = [y for y in range(0, count_cap + 1, y_step)]
    major_y_ticks = minor_y_ticks[::2]

    ax.set_xticks(x_values, tick_labels, fontsize=12)
    ax.set_yticks(minor_y_ticks, minor=True)
    ax.set_yticks(major_y_ticks, [str(y) for y in major_y_ticks], fontsize=12)

    for label in ax.get_xticklabels(which='major'):
        label.set(rotation=30, horizontalalignment='right')

    ax.set_title(title, {"fontsize": 24}, pad=10)

    ax.set_facecolor((0.1, 0.1, 0.1))
    ax.bar(x_values, games, label="Games", color="royalblue", edgecolor="black", hatch="//")
    ax.bar(x_values, wins, label="Win %", color="green", edgecolor="black", hatch="/")

    for x, y_games, y_wins in zip(x_values, games, wins):
        text_width = len(str(y_games)) * font_scale

        y_text = y_games + y_text_offset

        if 1 < y_games < max_count / 30:
            y_text = y_wins + 10

        ax.text(
            x - (text_width / 2),
            y_text,
            y_games,
            {"fontsize": 12, "color": "white", "fontweight": 800}
        )

        if y_wins > 0:
            win_pct = f"{(y_wins / y_games * 100):.1f}%"
            text_width = len(str(win_pct)) * (font_scale / 1.1)

            ax.text(
                x - (text_width / 2),
                y_wins + y_text_offset,
                win_pct,
                {"fontsize": 10, "color": "white", "fontweight": 800}
            )

    ax.legend(fontsize=14)

    plt.savefig("test.png", bbox_inches="tight")

def plot_lifetime_activity(database: GameDatabase):
    data = database.get_lifetime_activity()

    game_dates = [datetime(*map(int, f"{row[0]}-01".split("-"))) for row in data]
    games = [row[1] for row in data]
    wins = [row[2] for row in data]

    tick_labels = [date.strftime("%b %Y") for date in game_dates]

    title = "Games Per Month (Since 07-09-2020)"

    bar_plot(title, games, wins, 5, tick_labels, 0.18, 1.5)

def plot_weekday_activity(database: GameDatabase):
    data = database.get_weekday_activity()

    games = [row[1] for row in data[1:] + [data[0]]]
    wins = [row[2] for row in data]
    tick_labels = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

    title = "Games Per Weekday (Since 07-09-2020)"

    bar_plot(title, games, wins, 5, tick_labels, 0.06, 5)

def plot_hourly_activity(database: GameDatabase):
    data = database.get_hourly_activity()

    games = [row[1] for row in data]
    wins = [row[2] for row in data]
    tick_labels = [row[0] for row in data]

    title = "Games At Hours of the Day (Since 07-09-2020)"

    bar_plot(title, games, wins, 5, tick_labels, 0.16, 2)

def plot_dave_activity(database: GameDatabase):
    data = database.get_lifetime_activity()

    game_dates = [datetime(*map(int, f"{date_str}-01".split("-"))) for date_str, _ in data]
    counts = [10 for _ in data]

    tick_labels = [date.strftime("%b %Y") for date in game_dates]

    title = "Dave's Poon Level (Since 07-09-2020)"

    bar_plot(title, counts, 5, tick_labels, 0.18, 1.5)

def plot_teamcomp_winrate(database: GameDatabase):
    pass

PLOT_FUNCS = {
    "lifetime": plot_lifetime_activity,
    "weekday": plot_weekday_activity,
    "hourly": plot_hourly_activity,
    "dave": plot_dave_activity,
    "comp": plot_teamcomp_winrate,
}

PARSER = argparse.ArgumentParser()

PARSER.add_argument("game", choices=SUPPORTED_GAMES)
PARSER.add_argument("plot", choices=PLOT_FUNCS)

ARGS = PARSER.parse_args()

CONFIG = Config()
DATABASE = get_database_client(ARGS.game, CONFIG)

PLOT_FUNCS[ARGS.plot](DATABASE)
