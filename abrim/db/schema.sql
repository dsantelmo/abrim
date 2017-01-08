DROP TABLE IF EXISTS users;

DROP TABLE IF EXISTS items;

DROP TABLE IF EXISTS shadows;

DROP TABLE IF EXISTS edits;

CREATE TABLE IF NOT EXISTS users (
  user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  nickname      TEXT    NOT NULL,
  password      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
  item_id       TEXT    PRIMARY KEY ,
  user_id       TEXT    NOT NULL,
  node_id       TEXT    NOT NULL,
  content       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS shadows (
  shadow_id     INTEGER PRIMARY KEY,
  shadow        TEXT    NOT NULL,
  client_ver    INTEGER NOT NULL,
  server_ver    INTEGER NOT NULL,
  item_id       TEXT    NOT NULL,
  user_id       TEXT    NOT NULL,
  node_id       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS edits (
  edit_id       INTEGER PRIMARY KEY,
  edit          TEXT    NOT NULL,
  client_ver    INTEGER NOT NULL,
  server_ver    INTEGER NOT NULL,
  item_id       TEXT    NOT NULL,
  user_id       TEXT    NOT NULL,
  node_id       TEXT    NOT NULL
);
