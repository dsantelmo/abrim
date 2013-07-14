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

def _init_db(con):
    cur = con.cursor()
    # types:
    # - factotum: client and sync roles
    # - client: modifies notes, syncs to remote but does not accept conns
    # - sync: interconnects (client) nodes, does not modify notes but stores
    # - proxy: interconnects nodes, but only stores a small volatile buffer
    # - backup: sync-like secondary node, for backups only
    # - view: like sync, but allowing read only access of notes
    cur.execute("""CREATE TABLE IF NOT EXISTS node_info
      (node_uuid TEXT,
       node_type TEXT,
       node_url TEXT,
       last_seen INT,
       hostname TEXT,
       platform TEXT,
       processor TEXT
       )""")
    # diff types:
    # - nodiff: full text in each diff
    # - lines: diff by line
    # - chars: diff by chars
    # - bin: binary diff
    cur.execute("""CREATE TABLE IF NOT EXISTS notes
      (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
       stamp INT,
       node_uuid TEXT,
       note_uuid TEXT,
       change_uuid TEXT,
       prev_change_uuid TEXT,
       text TEXT,
       action TEXT,
       diff_type TEXT)""")
    cur.execute("""SELECT node_uuid FROM node_info
                   WHERE node_url IS NULL
                   AND last_seen IS NULL""")
    node_uuid = cur.fetchone()
    if node_uuid is None:
        node_uuid = uuid.uuid4().hex
        insert = (node_uuid,
                  'unknown', #node_type
                  None, #node_url
                  None, #last_seen
                  platform.node(), #hostname
                  platform.platform(), #platform
                  platform.processor(), #processor
                  )
        cur.execute("""INSERT OR IGNORE INTO node_info
                       (node_uuid,
                        node_type,
                        node_url,
                        last_seen,
                        hostname,
                        platform,
                        processor)
                       VALUES (?,?,?,?,?,?,?)""", insert)
    con.commit()
    return cur

#FIXME ugly, redundant code...
#FIXME abstract database access
def _create_note(node_uuid,note_text):
    with sqlite3.connect(db_path) as con:
        cur = _init_db(con)
        note_uuid = uuid.uuid4().hex
        inserts = (node_uuid, # node_uuid
                   note_uuid, # note_uuid
                   note_uuid, # change_uuid
                   None, # prev_change_uuid
                   note_text, # text
                   'NEW', # action
                   'nodiff',) # diff_type
        #FIXME Y2038?
        cur.execute("""INSERT OR IGNORE INTO notes
                       (stamp,
                        node_uuid,
                        note_uuid,
                        change_uuid,
                        prev_change_uuid,
                        text,
                        action,
                        diff_type)
                       VALUES (DATETIME('now'),?,?,?,?,?,?,?)""", inserts)
        cur.execute('SELECT last_insert_rowid()')
        note_id = cur.fetchone()
        con.commit()
        #FIXME control SQLITE_FULL
        cur.execute("SELECT * FROM notes WHERE id = ?", note_id)
        return (cur.fetchone())

def _modify_note(node_uuid, note_uuid, note_text):
    with sqlite3.connect(db_path) as con:
        cur = _init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE note_uuid = ?
                       ORDER BY stamp DESC LIMIT 1""", (note_uuid,))
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
        else:
            return "ERROR"

def _delete_note(node_uuid, note_uuid):
   with sqlite3.connect(db_path) as con:
        cur = _init_db(con)
        cur.execute("""SELECT id, action FROM notes WHERE note_uuid = ?
                       ORDER BY stamp DESC LIMIT 1""", (note_uuid,))
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

