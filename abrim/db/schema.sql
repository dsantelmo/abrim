DROP TABLE IF EXISTS users;
CREATE TABLE users (
  user_id   TEXT PRIMARY KEY,
  nickname  TEXT    NOT NULL,
  password  TEXT    NOT NULL
);

DROP TABLE IF EXISTS texts;
CREATE TABLE texts (
  text_id       TEXT PRIMARY KEY,
  content       TEXT NOT NULL,
  shadow        TEXT,
  user_id       TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
