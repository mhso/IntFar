PRAGMA journal_mode = 'wal';

CREATE TABLE [users] (
    [disc_id] INTEGER NOT NULL,
    [ingame_name] NVARCHAR(64) NOT NULL,
    [ingame_id] INTEGER NOT NULL,
    [match_auth_code] INTEGER NOT NULL,
    [latest_match_token] NVARCHAR(64) NOT NULL,
    [main] INTEGER(1),
    [active] INTEGER DEFAULT(1)
);
CREATE TABLE [games] (
    [game_id] NVARCHAR(64) PRIMARY KEY,
    [timestamp] INTEGER,
    [duration] INTEGER,
    [intfar_id] INTEGER,
    [intfar_reason] NVARCHAR(32),
    [win] INTEGER(1),
    [guild_id] INTEGER,
    [map_id] NVARCHAR(32),
    [started_t] INTEGER(1),
    [rounds_us] INTEGER(4),
    [rounds_them] INTEGER(4)
);
CREATE TABLE [participants] (
    [game_id] NVARCHAR(64) NOT NULL,
    [disc_id] INTEGER NOT NULL,
    [doinks] NVARCHAR(10),
    [kills] INTEGER,
    [deaths] INTEGER,
    [assists] INTEGER,
    [kda] REAL,
    [kp] INTEGER,
    [mvps] INTEGER,
    [score] INTEGER,
    [headshot_pct] INTEGER,
    [adr] INTEGER,
    [utility_damage] INTEGER,
    [enemies_flashed] INTEGER,
    [teammates_flashed] INTEGER,
    [flash_assists] INTEGER,
    [team_kills] INTEGER,
    [suicides] INTEGER,
    [accuracy] INTEGER,
    [entries] INTEGER,
    [triples] INTEGER,
    [quads] INTEGER,
    [aces] INTEGER,
    [one_v_ones_tried] INTEGER,
    [one_v_ones_won] INTEGER,
    [one_v_twos_tried] INTEGER,
    [one_v_twos_won] INTEGER,
    [one_v_threes_tried] INTEGER,
    [one_v_threes_won] INTEGER,
    [one_v_fours_tried] INTEGER,
    [one_v_fours_won] INTEGER,
    [one_v_fives_tried] INTEGER,
    [one_v_fives_won] INTEGER,
    [rank] INTEGER,
    PRIMARY KEY (game_id, disc_id)
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