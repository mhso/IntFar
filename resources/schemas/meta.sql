PRAGMA journal_mode = 'wal';

CREATE TABLE [users] (
    [disc_id] INTEGER PRIMARY KEY,
    [secret] NVARCHAR(32) NOT NULL,
    [reports] INTEGER DEFAULT(0)
);
CREATE TABLE [betting_balance] (
    [disc_id] INTEGER PRIMARY KEY,
    [tokens] INTEGER
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
    [disc_id] INTEGER PRIMARY KEY,
    [game] NVARCHAR(64) NULL
);