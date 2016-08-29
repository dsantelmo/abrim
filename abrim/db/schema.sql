DROP TABLE IF EXISTS users;
CREATE TABLE users (
  user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname  TEXT    NOT NULL,
  password  TEXT    NOT NULL
);

DROP TABLE IF EXISTS texts;
CREATE TABLE texts (
  text_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  content       TEXT NOT NULL,
  shadow        TEXT,
  user_id       INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
