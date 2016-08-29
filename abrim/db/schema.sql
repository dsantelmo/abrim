drop table if exists texts;
create table texts (
  --id integer primary key autoincrement,
  'client_id' text primary key not null,
--  'client_text' text not null,
--  'client_shadow' text not null
  'client_text' text,
  'client_shadow' text
);