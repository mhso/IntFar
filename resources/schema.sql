CREATE TABLE [users] (
    [disc_id] INTEGER PRIMARY KEY,
    [secret] NVARCHAR(32) NOT NULL,
    [reports] INTEGER
);
CREATE TABLE [users_lol] (
    [disc_id] INTEGER NOT NULL,
    [ingame_name] NVARCHAR(64) NOT NULL,
    [ingame_id] NVARCHAR(64) NOT NULL,
    [main] INTEGER(1),
    [active] INTEGER DEFAULT(1)
);
CREATE TABLE [users_csgo] (
    [disc_id] INTEGER NOT NULL,
    [ingame_name] NVARCHAR(64) NOT NULL,
    [ingame_id] INTEGER NOT NULL,
    [match_auth_code] INTEGER NOT NULL,
    [latest_match_token] NVARCHAR(64) NOT NULL,
    [main] INTEGER(1),
    [active] INTEGER DEFAULT(1)
);
CREATE TABLE [games_lol] (
    [game_id] NVARCHAR(64) PRIMARY KEY,
    [timestamp] INTEGER,
    [duration] INTEGER,
    [intfar_id] INTEGER,
    [intfar_reason] NVARCHAR(4),
    [win] INTEGER(1),
    [guild_id] INTEGER,
    [first_blood] INTEGER
);
CREATE TABLE [games_csgo] (
    [game_id] NVARCHAR(64) PRIMARY KEY,
    [timestamp] INTEGER,
    [duration] INTEGER,
    [intfar_id] INTEGER,
    [intfar_reason] NVARCHAR(4),
    [win] INTEGER(1),
    [guild_id] INTEGER
    [map] NVARCHAR(32),
    [rounds_t] INTEGER(4),
    [rounds_ct] INTEGER(4)
);
CREATE TABLE [missed_games] (
    [game_id] NVARCHAR(64) NOT NULL,
    [game] NVARCHAR(64) NOT NULL,
    [guild_id] INTEGER NOT NULL,
    [timestamp] INTEGER,
    PRIMARY KEY (game_id, game)
);
CREATE TABLE [participants_lol] (
    [game_id] NVARCHAR(64) NOT NULL,
    [disc_id] INTEGER NOT NULL,
    [doinks] NVARCHAR(10),
    [kills] INTEGER,
    [deaths] INTEGER,
    [assists] INTEGER,
    [kda] REAL,
    [kp] INTEGER,
    [champ_id] INTEGER NOT NULL,
    [damage] INTEGER,
    [cs] INTEGER,
    [cs_per_min] REAL,
    [gold] INTEGER,
    [vision_wards] INTEGER,
    [vision_score] INTEGER,
    [steals] INTEGER,
    PRIMARY KEY (game_id, disc_id)
);
CREATE TABLE [participants_csgo] (
    [game_id] NVARCHAR(64) NOT NULL,
    [disc_id] INTEGER NOT NULL,
    [champ_id] INTEGER NOT NULL,
    [doinks] NVARCHAR(10),
    [kills] INTEGER,
    [deaths] INTEGER,
    [assists] INTEGER,
    [kda] REAL,
    [damage] INTEGER,
    [cs] INTEGER,
    [cs_per_min] INTEGER,
    [gold] INTEGER,
    [kp] INTEGER,
    [vision_wards] INTEGER,
    [vision_score] INTEGER,
    [steals] INTEGER,
    PRIMARY KEY (game_id, disc_id)
);
CREATE TABLE [betting_balance] (
    [disc_id] INTEGER PRIMARY KEY,
    [tokens] INTEGER
);
CREATE TABLE [bets] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [better_id] INTEGER NOT NULL,
    [guild_id] INTEGER NOT NULL,
    [game_id] NVARCHAR(64),
    [game] NVARCHAR(64),
    [timestamp] INTEGER NOT NULL,
    [event_id] NVARCHAR(32) NOT NULL,
    [amount] INTEGER NOT NULL,
    [game_duration] INTEGER DEFAULT(0),
    [target] INTEGER,
    [ticket] INTEGER,
    [result] INTEGER(2),
    [payout] INTEGER
);
CREATE TABLE [event_sounds] (
    [disc_id] INTEGER NOT NULL,
    [game] NVARCHAR(64) NOT NULL,
    [sound] NVARCHAR(24) NOT NULL,
    [event] NVARCHAR(6) NOT NULL,
    PRIMARY KEY (disc_id, game, event)
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
CREATE TABLE [champ_lists] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [name] NVARCHAR(32) NOT NULL UNIQUE,
    [owner_id] INTEGER NOT NULL
);
CREATE TABLE [list_items] (
    [id] INTEGER PRIMARY KEY AUTOINCREMENT,
    [champ_id] INTEGER NOT NULL,
    [list_id] INTEGER NOT NULL,
    UNIQUE(champ_id, list_id)
);