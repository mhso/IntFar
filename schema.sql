CREATE TABLE [registered_summoners] (
    [disc_id] NVARCHAR(64) NOT NULL PRIMARY KEY,
    [summ_name] NVARCHAR(64) NOT NULL,
    [summ_id] NVARCHAR(64) NOT NULL
);
CREATE TABLE [best_stats] (
    [game_id] INTEGER NOT NULL PRIMARY KEY,
    [int_far] INTEGER,
    [kills] INTEGER,
    [kills_id] INTEGER,
    [deaths] INTEGER,
    [deaths_id] INTEGER,
    [kda] REAL,
    [kda_id] INTEGER,
    [damage] INTEGER,
    [damage_id] INTEGER,
    [cs] INTEGER,
    [cs_id] INTEGER,
    [gold] INTEGER,
    [gold_id] INTEGER,
    [kp] INTEGER,
    [kp_id] INTEGER,
    [vision_wards] INTEGER,
    [vision_wards_id] INTEGER,
    [vision_score] INTEGER,
    [vision_score_id] INTEGER
);
CREATE TABLE [worst_stats] (
    [game_id] INTEGER NOT NULL PRIMARY KEY,
    [int_far] INTEGER,
    [kills] INTEGER,
    [kills_id] INTEGER,
    [deaths] INTEGER,
    [deaths_id] INTEGER,
    [kda] REAL,
    [kda_id] INTEGER,
    [damage] INTEGER,
    [damage_id] INTEGER,
    [cs] INTEGER,
    [cs_id] INTEGER,
    [gold] INTEGER,
    [gold_id] INTEGER,
    [kp] INTEGER,
    [kp_id] INTEGER,
    [vision_wards] INTEGER,
    [vision_wards_id] INTEGER,
    [vision_score] INTEGER,
    [vision_score_id] INTEGER
);