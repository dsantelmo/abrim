DROP TABLE IF EXISTS users;
CREATE TABLE users (
  user_id   TEXT PRIMARY KEY,
  nickname  TEXT    NOT NULL,
  password  TEXT    NOT NULL
);

DROP TABLE IF EXISTS items;
CREATE TABLE items (
  item_id       TEXT PRIMARY KEY,
  content       TEXT,
  shadow        TEXT,
  user_id       TEXT NOT NULL,
  node_id       TEXT NOT NULL--,
  --FOREIGN KEY(user_id) REFERENCES users(user_id)
);
