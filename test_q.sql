-- disable foreign key constraint check
PRAGMA foreign_keys=off;

-- start a transaction
BEGIN TRANSACTION;

-- Here you can drop column
CREATE TABLE IF NOT EXISTS new_table( 
  game_id INTEGER NOT NULL,
  disc_id INTEGER NOT NULL,
  timestamp INTEGER,
  doinks NVARCHAR(6)
);
-- copy data from the table to the new_table
INSERT INTO new_table(game_id, disc_id, timestamp, doinks)
SELECT game_id, disc_id, timestamp, doinks
FROM participants;

-- drop the table
DROP TABLE participants;

-- rename the new_table to the table
ALTER TABLE new_table RENAME TO participants; 

-- commit the transaction
COMMIT;

-- enable foreign key constraint check
PRAGMA foreign_keys=on;