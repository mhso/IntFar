CREATE TABLE [registered_summoners] (
    [disc_id] INTEGER NOT NULL,
    [summ_name] NVARCHAR(64) NOT NULL,
    [summ_id] NVARCHAR(64) NOT NULL,
    [secret] NVARCHAR(32) NOT NULL,
    [reports] INTEGER,
    [active] INTEGER DEFAULT(1),
    PRIMARY KEY (disc_id, summ_id)
);
CREATE TABLE [games] (
  [game_id] INTEGER PRIMARY KEY,
  [timestamp] INTEGER,
  [intfar_id] INTEGER,
  [intfar_reason] NVARCHAR(4),
  [guild_id] INTEGER
);
CREATE TABLE [participants] (
  [game_id] INTEGER NOT NULL,
  [disc_id] INTEGER NOT NULL,
  [doinks] NVARCHAR(10),
  PRIMARY KEY (game_id, disc_id)
);
CREATE TABLE [best_stats] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [game_id] INTEGER UNIQUE NOT NULL,
    [first_blood] INTEGER,
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
    [cs_per_min] REAL,
    [cs_per_min_id] INTEGER,
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
    [game_id] INTEGER UNIQUE NOT NULL,
    [first_blood] INTEGER,
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
    [cs_per_min] REAL,
    [cs_per_min_id] INTEGER,
    [gold] INTEGER,
    [gold_id] INTEGER,
    [kp] INTEGER,
    [kp_id] INTEGER,
    [vision_wards] INTEGER,
    [vision_wards_id] INTEGER,
    [vision_score] INTEGER,
    [vision_score_id] INTEGER
);
CREATE TABLE [betting_balance] (
    [disc_id] INTEGER PRIMARY KEY,
    [tokens] INTEGER
);
CREATE TABLE [betting_events] (
    [id] INTEGER PRIMARY KEY,
    [max_return] DECIMAL NOT NULL
);
CREATE TABLE [bets] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [better_id] INTEGER NOT NULL,
    [guild_id] INTEGER NOT NULL,
    [game_id] INTEGER,
    [timestamp] INTEGER NOT NULL,
    [event_id] INTEGER NOT NULL,
    [amount] INTEGER NOT NULL,
    [game_duration] INTEGER DEFAULT(0),
    [target] INTEGER,
    [ticket] INTEGER,
    [result] INTEGER(2),
    [payout] INTEGER
);
CREATE TABLE [shop_items] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [name] NVARCHAR(64) NOT NULL,
    [price] INTEGER NOT NULL,
    [seller_id] INTEGER
);
CREATE TABLE [owned_items] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [name] NVARCHAR(64) NOT NULL,
    [owner_id] INTEGER NOT NULL
);