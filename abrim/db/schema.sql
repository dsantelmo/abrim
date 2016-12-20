--DROP TABLE IF EXISTS users;

--DROP TABLE IF EXISTS items;

CREATE TABLE IF NOT EXISTS users (
  user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname  TEXT    NOT NULL,
  password  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  content       TEXT,
  shadow        TEXT,
  user_id       TEXT NOT NULL,
  node_id       TEXT NOT NULL--,
  --FOREIGN KEY(user_id) REFERENCES users(user_id)
);
