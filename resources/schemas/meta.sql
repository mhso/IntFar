PRAGMA journal_mode = 'wal';

CREATE TABLE [users] (
    [disc_id] INTEGER PRIMARY KEY,
    [secret] NVARCHAR(64) NOT NULL,
    [reports] INTEGER DEFAULT(0)
);
CREATE TABLE [betting_balance] (
    [disc_id] INTEGER PRIMARY KEY,
    [tokens] INTEGER
);
CREATE TABLE [sounds] (
    [sound] NVARCHAR(24) PRIMARY KEY,
    [owner_id] INTEGER NOT NULL,
    [timestamp] INTEGER NOT NULL
);
CREATE TABLE [sound_hits] (
    [sound] NVARCHAR(24) NOT NULL,
    [start_date] INTEGER NOT NULL,
    [end_date] INTEGER NOT NULL,
    [plays] INTEGER DEFAULT(0),
    PRIMARY KEY(sound, start_date)
);
CREATE TABLE [join_sounds] (
    [disc_id] INTEGER PRIMARY KEY,
    [sound] NVARCHAR(24) NOT NULL
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
    [arguments] BLOB NOT NULL,
    [result] BLOB NULL
);
CREATE TABLE [default_game] (
    [disc_id] INTEGER PRIMARY KEY,
    [game] NVARCHAR(64) NULL
);