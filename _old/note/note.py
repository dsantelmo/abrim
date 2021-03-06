#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import uuid
import json
import sys
import urllib2
from os import makedirs
import os.path
import platform
import note_db
try:
    import appdirs
    udd = appdirs.user_data_dir("abrim","abrim_notes")
    db_path = os.path.join(udd, 'abrimnotes.sqlite')
    if not os.path.exists(udd):
        makedirs(udd)
except ImportError:
    try:
        db_path = "." \
                  + os.path.basename(sys.modules['__main__'].__file__) \
                  + ".sqlite"
    except AttributeError:
        db_path='.notes.sqlite'

#FIXME globals for node_uuid, db_path...
node_uuid = None

def __usage_exit():
    print "USAGE" #FIXME
    sys.exit(1)


def __to_json(inp):
    return json.dumps(inp, sort_keys=True,
                      indent=4, separators=(',', ': '))

def create(note_text=''):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        note_text = ' '.join(sys.argv[2:])
    return note_db._create_note(node_uuid, note_text)

def modify(note_uuid='', note_text=''):
    if __name__ == '__main__':
        if len(sys.argv) < 4:
            __usage_exit()
        note_uuid = sys.argv[2]
        note_text = ' '.join(sys.argv[3:])
    return note_db._modify_note(node_uuid, note_uuid, note_text)

def delete(note_uuid=''):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        note_uuid = sys.argv[2]
    return note_db._delete_note(node_uuid, note_uuid)


def list_notes():
    with sqlite3.connect(db_path) as con:
        cur = note_db._init_db(con)
        cur.execute("""SELECT a.stamp, a.change_uuid, a.note_uuid, a.action
                       FROM notes a
                       INNER JOIN (SELECT id, note_uuid FROM notes
                                   GROUP BY note_uuid ORDER BY stamp DESC) b
                       ON a.id = b.id WHERE a.action <> 'DEL'
                       ORDER BY a.stamp ASC""")
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
        cur = note_db._init_db(con)
        cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                       FROM notes ORDER BY stamp DESC
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

def changes_before_id(change_id,num=0):
    if num < 1:
        num = -1
    with sqlite3.connect(db_path) as con:
        cur = note_db._init_db(con)
        cur.execute("""SELECT id FROM notes WHERE change_uuid = ?
                       LIMIT 1""", (change_id,))
        note_id = cur.fetchone()
        ret_list = "ERROR"
        if note_id is not None:
            cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                           FROM notes WHERE id < ? LIMIT ?""",
                           (note_id[0],num))
            notes = cur.fetchall() #FIXME paginate?
            ret_list = []
            for note in notes:
                ret_list.append({'stamp': str(note[0]),
                                 'change_uuid': str(note[1]),
                                 'note_uuid': str(note[2]),
                                 'action': str(note[3]),
                                 })
        return __to_json(ret_list)

def changes_since_id(change_id,num=0):
    if num < 1:
        num = -1
    with sqlite3.connect(db_path) as con:
        cur = note_db._init_db(con)
        cur.execute("""SELECT id FROM notes WHERE change_uuid = ?
                       LIMIT 1""", (change_id,))
        note_id = cur.fetchone()
        ret_list = "ERROR"
        if note_id is not None:
            cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                           FROM notes WHERE id > ? LIMIT ?""",
                           (note_id[0],num))
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
        cur = note_db._init_db(con)
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
        cur = note_db._init_db(con)
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

def say_db():
    return db_path

def __get_last_change():
    with sqlite3.connect(db_path) as con:
        cur = note_db._init_db(con)
        cur.execute("""SELECT stamp, change_uuid, note_uuid, action
                       FROM notes ORDER BY stamp DESC LIMIT 1""")
        return cur.fetchone()

def __get_remote_list(url):
    try:
        return json.loads(urllib2.urlopen(url + '/list/').read())
    except ValueError:
        print "ValueError"
        sys.exit(1) #FIXME
    except urllib2.URLError:
        print "URLError"
        sys.exit(1) #FIXME

def __get_remote_change_by_id(url, change_uuid):
    try:
        url = url + '/get_change_by_id/' + change_uuid
        return json.loads(urllib2.urlopen(url).read())
    except ValueError:
        print "ValueError"
        sys.exit(1) #FIXME
    except urllib2.URLError:
        print "URLError"
        sys.exit(1) #FIXME

def __insert_remote_list(url, notes_list):
    with sqlite3.connect(db_path) as con:
        cur = note_db._init_db(con)
        inserts = []
        for note in notes_list:
            change = __get_remote_change_by_id(url, note['change_uuid'])
            insert = (note['stamp'],
                      note['change_uuid'],
                      note['note_uuid'],
                      change['text'],
                      note['action'],)
            inserts.append(insert)
        cur.executemany("""INSERT OR IGNORE INTO notes
                       (stamp, change_uuid, note_uuid, text, action)
                       VALUES (?,?,?,?,?)""", inserts)
        con.commit()
        return len(inserts)

def sync(url=None):
    if __name__ == '__main__':
        if len(sys.argv) < 3:
            __usage_exit()
        url = sys.argv[2]
    if url is None:
        sys.exit(1) #FIXME
    try:
        stamp, c_uuid, n_uuid, action = __get_last_change()
        # if there are changes start partial sync
        # check summary
        # ask for the changes from last common change
        # merge, push changes, finish sync
    except TypeError:
        # no changes, full sync
        new_notes_num = __insert_remote_list(url, __get_remote_list(url))
        return "Full sync. %d new note(s)" % new_notes_num
        #FIXME also sync history
        #FIXME this assumes that both systems have a correct time in clock
        # sync full history here



with sqlite3.connect(db_path) as con:
    note_db._init_db(con)

if __name__ == '__main__':
    try:
        cli_options = {
          'create' : create,
          'modify' : modify,
          'delete' : delete,
          'list' : list_notes,
          'sync' : sync,
          'db' : say_db,
        }
        outp = cli_options[sys.argv[1]]()
        print outp
        sys.exit(0)
    except KeyError:
        __usage_exit()

