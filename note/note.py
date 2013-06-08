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
       change_uuid TEXT,
       note_uuid TEXT,
       text TEXT,
       action TEXT)""")
    return cur

#FIXME ugly, redundant code...
#FIXME abstract database access
def create(note_text=''):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        note_text = ' '.join(sys.argv[2:])
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        stamp = int(datetime.datetime.utcnow().strftime('%s'))
        note_uuid = uuid.uuid4().hex
        inserts = (stamp, note_uuid, note_uuid, note_text, 'NEW')
        cur.execute("""INSERT OR IGNORE INTO notes
                       (stamp, change_uuid, note_uuid, text, action)
                       VALUES (?,?,?,?,?)""", inserts)
        cur.execute('SELECT last_insert_rowid()')
        note_id = cur.fetchone()
        con.commit()
        #FIXME control SQLITE_FULL
        cur.execute("SELECT * FROM notes WHERE id = ?", note_id)
        return (cur.fetchone())

def modify(note_uuid='', note_text=''):
    if __name__ == '__main__':
        if len(sys.argv) < 4:
            __usage_exit()
        note_uuid = sys.argv[2]
        note_text = ' '.join(sys.argv[3:])
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE note_uuid = ?
                       ORDER BY id DESC LIMIT 1""", (note_uuid,))
        note = cur.fetchone()
        action = 'MOD'
        if note is None:
            return "ERROR: that note doesn't exist."
            action = 'ERROR'
        elif note[1] == 'DEL':
            return "WARN: that note was deleted. Re-creating"
        if action != 'ERROR':
            stamp = int(datetime.datetime.utcnow().strftime('%s'))
            change_uuid = uuid.uuid4().hex
            insert = (stamp, change_uuid, note_uuid, note_text, action)
            cur.execute("""INSERT INTO notes
                           (stamp, change_uuid, note_uuid, text, action)
                           VALUES (?,?,?,?,?)""", insert)
            con.commit()
            return "OK"

def delete(note_uuid=''):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        note_uuid = sys.argv[2]
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE note_uuid = ?
                       ORDER BY id DESC LIMIT 1""", (note_uuid,))
        note = cur.fetchone()
        if note is None or note[1] == 'DEL':
            return "ERROR: that note didn't exist."
            sys.exit(1) #FIXME
        stamp = int(datetime.datetime.utcnow().strftime('%s'))
        change_uuid = uuid.uuid4().hex
        insert = (stamp, change_uuid, note_uuid, '', 'DEL')
        cur.execute("""INSERT INTO notes
                       (stamp, change_uuid, note_uuid, text, action)
                       VALUES (?,?,?,?,?)""", insert)
        con.commit()
        return "OK"


def list():
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT a.note_uuid, a.text FROM notes a
                       INNER JOIN (SELECT id, note_uuid FROM notes
                                   GROUP BY note_uuid ORDER BY id DESC) b
                       ON a.id = b.id WHERE a.action <> 'DEL'
                       ORDER BY a.id ASC""")
        notes = cur.fetchall() #FIXME paginate?
        outp = ""
        for note in notes:
            outp = outp + note[0] + ": " + note[1] + "\n"
        return outp

if __name__ == '__main__':
    try:
        cli_options = {
          'create' : create,
          'modify' : modify,
          'delete' : delete,
          'list' : list,
        }
        outp = cli_options[sys.argv[1]]()
        print outp
        sys.exit(0)
    except KeyError:
        __usage_exit()

