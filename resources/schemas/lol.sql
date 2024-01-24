PRAGMA journal_mode = 'wal';

CREATE TABLE [users] (
    [disc_id] INTEGER NOT NULL,
    [ingame_name] NVARCHAR(64) NOT NULL,
    [ingame_id] NVARCHAR(64) NOT NULL,
    [main] INTEGER(1),
    [active] INTEGER DEFAULT(1)
);
CREATE TABLE [games] (
    [game_id] NVARCHAR(64) PRIMARY KEY,
    [timestamp] INTEGER,
    [duration] INTEGER,
    [intfar_id] INTEGER,
    [intfar_reason] NVARCHAR(4),
    [win] INTEGER(2),
    [guild_id] INTEGER,
    [first_blood] INTEGER
);
CREATE TABLE [participants] (
    [game_id] NVARCHAR(64) NOT NULL,
    [disc_id] INTEGER NOT NULL,
    [kills] INTEGER,
    [deaths] INTEGER,
    [assists] INTEGER,
    [doinks] NVARCHAR(10),
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
CREATE TABLE [missed_games] (
    [game_id] NVARCHAR(64) NOT NULL,
    [guild_id] INTEGER NOT NULL,
    [timestamp] INTEGER,
    PRIMARY KEY (game_id, game)
);
CREATE TABLE [event_sounds] (
    [disc_id] INTEGER NOT NULL,
    [sound] NVARCHAR(24) NOT NULL,
    [event] NVARCHAR(6) NOT NULL,
    PRIMARY KEY (disc_id, game, event)
);