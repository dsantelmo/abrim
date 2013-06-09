#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import uuid
import json
import sys

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

def __to_json(inp):
    return json.dumps(inp, sort_keys=True,
                      indent=4, separators=(',', ': '))

#FIXME ugly, redundant code...
#FIXME abstract database access
def create(note_text=''):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        note_text = ' '.join(sys.argv[2:])
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        note_uuid = uuid.uuid4().hex
        inserts = (note_uuid, note_uuid, note_text, 'NEW')
        #FIXME Y2038?
        cur.execute("""INSERT OR IGNORE INTO notes
                       (stamp, change_uuid, note_uuid, text, action)
                       VALUES (DATETIME('now'),?,?,?,?)""", inserts)
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
            change_uuid = uuid.uuid4().hex
            insert = (change_uuid, note_uuid, note_text, action)
            cur.execute("""INSERT INTO notes
                           (stamp, change_uuid, note_uuid, text, action)
                           VALUES (DATETIME('now'),?,?,?,?)""", insert)
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
        change_uuid = uuid.uuid4().hex
        insert = (change_uuid, note_uuid, '', 'DEL')
        cur.execute("""INSERT INTO notes
                       (stamp, change_uuid, note_uuid, text, action)
                       VALUES (DATETIME('now'),?,?,?,?)""", insert)
        con.commit()
        return "OK"


def list():
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT a.stamp, a.change_uuid, a.note_uuid, a.action
                       FROM notes a
                       INNER JOIN (SELECT id, note_uuid FROM notes
                                   GROUP BY note_uuid ORDER BY id DESC) b
                       ON a.id = b.id WHERE a.action <> 'DEL'
                       ORDER BY a.id ASC""")
        notes = cur.fetchall() #FIXME paginate?
        ret_list = []
        for note in notes:
            ret_list.append({'stamp': str(note[0]),
                             'change_uuid': str(note[1]),
                             'note_uuid': str(note[2]),
                             'action': str(note[3]),
                             })
        return __to_json(ret_list)

def last(changes_num=0):
    limit = 100
    if changes_num > limit or changes_num < 1:
        changes_num = limit
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                       FROM notes ORDER BY ID DESC
                       LIMIT """ + str(changes_num))
        notes = cur.fetchall() #FIXME paginate?
        ret_list = []
        for note in notes:
            ret_list.append({'stamp': str(note[0]),
                             'change_uuid': str(note[1]),
                             'note_uuid': str(note[2]),
                             'action': str(note[3]),
                             })
        return __to_json(ret_list)

def changes_since_id(change_id):
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id FROM notes WHERE change_uuid = ?
                       LIMIT 1""", (change_id,))
        note_id = cur.fetchone()
        ret_list = "ERROR"
        if note_id is not None:
            cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                           FROM notes WHERE id > ?""",
                           (note_id[0],))
            notes = cur.fetchall() #FIXME paginate?
            ret_list = []
            for note in notes:
                ret_list.append({'stamp': str(note[0]),
                                 'change_uuid': str(note[1]),
                                 'note_uuid': str(note[2]),
                                 'action': str(note[3]),
                                 })
        return __to_json(ret_list)

def summ_changes_since_id(change_id):
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT id FROM notes WHERE change_uuid = ?
                       LIMIT 1""", (change_id,))
        note_id = cur.fetchone()
        ret_list = "ERROR"
        if note_id is not None:
            cur.execute("""SELECT action, count(action)
                           FROM notes WHERE id > ?
                           GROUP BY action""",
                           (note_id[0],))
            notes = cur.fetchall() #FIXME paginate?
            ret_list = []
            for note in notes:
                ret_dict = {}
                ret_dict[str(note[0])] = note[1]
                ret_list.append(ret_dict)
        return __to_json(ret_list)

def get_change_by_id(change_id):
    with sqlite3.connect(db_path) as con:
        cur = __init_db(con)
        cur.execute("""SELECT stamp, note_uuid, text, action
                       FROM notes WHERE change_uuid = ?""", (change_id,))
        ret_note = cur.fetchone()
        if ret_note is not None:
            return __to_json({'stamp': ret_note[0],
                    'note_uuid': ret_note[1],
                    'text': ret_note[2],
                    'action': ret_note[3],
                   })
        else:
            return __to_json("ERROR")

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

