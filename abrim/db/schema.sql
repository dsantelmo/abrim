drop table if exists texts;
create table texts (
  id integer primary key autoincrement,
  'text' text not null
);
