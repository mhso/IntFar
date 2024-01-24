PRAGMA journal_mode = 'wal';

CREATE TABLE [users] (
    [disc_id] INTEGER PRIMARY KEY,
    [secret] NVARCHAR(32) NOT NULL,
    [reports] INTEGER DEFAULT(0)
);
CREATE TABLE [missed_games] (
    [game_id] NVARCHAR(64) NOT NULL,
    [game] NVARCHAR(64) NOT NULL,
    [guild_id] INTEGER NOT NULL,
    [timestamp] INTEGER,
    PRIMARY KEY (game_id, game)
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
CREATE TABLE [command_queue] (
    [id] INTEGER NOT NULL,
    [target] NVARCHAR(64) NOT NULL,
    [command] NVARCHAR(64) NOT NULL,
    [arguments] NVARCHAR(128) NOT NULL,
    [result] NVARCHAR(128) NULL
);
CREATE TABLE [default_game] (
    [disc_id] INTEGER NOT NULL,
    [game] NVARCHAR(64) NULL
);