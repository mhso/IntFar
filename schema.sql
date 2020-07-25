CREATE TABLE [registered_summoners] (
    [disc_id] INTEGER NOT NULL PRIMARY KEY,
    [summ_name] NVARCHAR(64) NOT NULL,
    [summ_id] NVARCHAR(64) NOT NULL
);
CREATE TABLE [participants] (
  [game_id] INTEGER NOT NULL,
  [disc_id] INTEGER NOT NULL,
  [timestamp] INTEGER,
  [doinks] NVARCHAR(5)
);
CREATE TABLE [best_stats] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [game_id] INTEGER NOT NULL,
    [int_far] INTEGER,
    [intfar_reason] NVARCHAR(4),
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
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [game_id] INTEGER NOT NULL,
    [int_far] INTEGER,
    [intfar_reason] NVARCHAR(4),
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
