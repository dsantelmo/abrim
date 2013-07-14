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

