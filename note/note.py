#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import uuid
import sys
import datetime

db_path='_notes.sqlite'

def __usage_exit():
    print "USAGE" #FIXME
    sys.exit(1)

def __init_db(con):
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS notes
      (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
       stamp INT,
       uuid TEXT,
       text TEXT,
       action TEXT)""")
    return cur

#FIXME ugly, redundant code...
#FIXME abstract database access
def cli_create():
    if len(sys.argv) < 3:
        __usage_exit()
    note = ' '.join(sys.argv[2:])
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        stamp = int(datetime.datetime.utcnow().strftime('%s'))
        inserts = (stamp, uuid.uuid4().hex, note, 'NEW')
        cur.execute("""INSERT OR IGNORE INTO notes
                       (stamp, uuid, text, action) VALUES (?,?,?,?)""", inserts)
        cur.execute('SELECT last_insert_rowid()')
        note_id = cur.fetchone()
        con.commit()
        #FIXME control SQLITE_FULL
        cur.execute("SELECT * FROM notes WHERE id = ?", note_id)
        print (cur.fetchone())

def cli_modify():
    if len(sys.argv) < 4:
        __usage_exit()
    note_uuid = sys.argv[2]
    note_text = ' '.join(sys.argv[3:])
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE uuid = ?
                       ORDER BY id DESC LIMIT 1""", (note_uuid,))
        note = cur.fetchone()
        action = 'MOD'
        if note is None:
            print "That note doesn't exist."
            action = 'ERROR'
        elif note[1] == 'DEL':
            print "That note was deleted. Re-creating"
        if action != 'ERROR':
            stamp = int(datetime.datetime.utcnow().strftime('%s'))
            insert = (stamp, note_uuid, note_text, action)
            cur.execute("""INSERT INTO notes (stamp, uuid, text, action)
                           VALUES (?,?,?,?)""", insert)
            con.commit()

def cli_delete():
    if len(sys.argv) < 3:
        __usage_exit()
    note_uuid = sys.argv[2]
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE uuid = ?
                       ORDER BY id DESC LIMIT 1""", (note_uuid,))
        note = cur.fetchone()
        if note is None or note[1] == 'DEL':
            print "ERROR: that note didn't exist."
            sys.exit(1) #FIXME
        insert = ('', note_uuid, 'DEL')
        cur.execute("""INSERT INTO notes (text, uuid, action)
                       VALUES (?,?,?)""", insert)
        con.commit()


def cli_list():
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT a.uuid, a.text FROM notes a
                       INNER JOIN (SELECT id, uuid FROM notes
                                   GROUP BY uuid ORDER BY id DESC) b
                       ON a.id = b.id WHERE a.action <> 'DEL'
                       ORDER BY a.id ASC""")
        notes = cur.fetchall() #FIXME paginate?
        for note in notes:
            print note[0] + ": " + note[1]

try:
    cli_options = {
      'create' : cli_create,
      'modify' : cli_modify,
      'delete' : cli_delete,
      'list' : cli_list,
    }
    cli_options[sys.argv[1]]()
    sys.exit(0)
except KeyError:
    __usage_exit()

