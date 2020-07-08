CREATE TABLE [registered_summoners] (
    [disc_id] NVARCHAR(64) NOT NULL PRIMARY KEY,
    [summ_name] NVARCHAR(64) NOT NULL,
    [summ_id] NVARCHAR(64) NOT NULL
);
CREATE TABLE [game_stats] (
    [game_id] INTEGER NOT NULL PRIMARY KEY,
    [int_far] INTEGER,
    [most_kills] INTEGER,
    [most_kills_id] INTEGER,
    [fewest_deaths] INTEGER,
    [fewest_deaths_id] INTEGER,
    [highest_kda] REAL,
    [highest_kda_id] INTEGER,
    [most_damage] INTEGER,
    [most_damage_id] INTEGER,
    [most_cs] INTEGER,
    [most_cs_id] INTEGER,
    [most_gold] INTEGER,
    [most_gold_id] INTEGER,
    [highest_kp] INTEGER,
    [highest_kp_id] INTEGER,
    [highest_vision_score] INTEGER,
    [highest_vision_score_id] INTEGER
);