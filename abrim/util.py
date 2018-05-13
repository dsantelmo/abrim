#!/usr/bin/env python

import sys
import diff_match_patch
import logging
import os
import zlib
from pathlib import Path
import sqlite3
import random


def get_log(full_debug=False):
    if full_debug:
        # enable debug for HTTP requests
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
    else:
        # disable more with
        # for key in logging.Logger.manager.loggerDict:
        #    print(key)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('google').setLevel(logging.CRITICAL)

    # FIXME http://docs.python-guide.org/en/latest/writing/logging/
    # It is strongly advised that you do not add any handlers other
    # than NullHandler to your library's loggers.
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-5s %(asctime)s - %(module)-10s %(funcName)-25s %(lineno)-5d: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')  # ,
    # disable_existing_loggers=False)
    logging.StreamHandler(sys.stdout)
    return logging.getLogger(__name__)


log = get_log(full_debug=False)


class Db(object):
    def get_db_path(self):
        node_id = self.node_id
        filename = 'abrim_' + node_id + '.sqlite'
        try:
            # noinspection PyUnresolvedReferences
            import appdirs
            udd = appdirs.user_data_dir("abrim", "abrim_node")
            db_path = os.path.join(udd, filename)
            if not os.path.exists(udd):
                os.makedirs(udd)
        except ImportError:
            try:
                db_path = "." \
                          + os.path.basename(sys.modules['__main__'].__file__) \
                          + filename
            except AttributeError:
                db_path = filename + '_error.sqlite'
        self.db_path = db_path

    def drop_db(self):
        self.cur.executescript("""
            DROP TABLE IF EXISTS nodes;
            DROP TABLE IF EXISTS items;
            DROP TABLE IF EXISTS shadows;
            """)

        self.con.commit()

    def _init_db(self, con, drop_db):
        self.con = con
        self.cur = self.con.cursor()

        if drop_db:
            self.drop_db()

        self.cur.executescript("""CREATE TABLE IF NOT EXISTS nodes
           (id TEXT PRIMARY KEY NOT NULL,
            base_url TEXT
            );
            
           CREATE TABLE IF NOT EXISTS items
           (id TEXT PRIMARY KEY NOT NULL,
            text TEXT,
            node TEXT NOT NULL,
            FOREIGN KEY(node) REFERENCES nodes(id)
            );
            
           CREATE TABLE IF NOT EXISTS shadows
           (item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            rev INTEGER NOT NULL,
            other_node_rev INTEGER NOT NULL,
            shadow TEXT,
            PRIMARY KEY(item, other_node, rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );
            
           CREATE TABLE IF NOT EXISTS edits
           (item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            rev INTEGER NOT NULL,
            other_node_rev INTEGER NOT NULL,
            edits TEXT,
            old_shadow_adler32 TEXT,
            shadow_adler32 TEXT,
            PRIMARY KEY(item, other_node, rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );
            
            """)

        self.con.commit()

        self.start_transaction("init the DB")
        try:
            self.cur.execute("""SELECT id FROM nodes
                           WHERE base_url IS NULL""")
            node_uuid = self.cur.fetchone()
            if node_uuid is None:
                node_uuid = "node_1"  # uuid.uuid4().hex
                insert = (node_uuid,
                          None
                          )
                self.cur.execute("""INSERT OR IGNORE INTO nodes
                               (id,
                                base_url)
                               VALUES (?,?)""", insert)
            self._log_debug_trans("_init_db done")
            self.end_transaction()
        except Exception as err:
            self._log_debug_trans("rollback in _init_db")
            log.error(err)
            self.cur.execute("rollback")
            raise

    def add_known_node(self, node_id, url):
        insert = (node_id,
                  url)
        self.cur.execute("""INSERT OR IGNORE INTO nodes
                           (id,
                            base_url)
                           VALUES (?,?)""", insert)
        self.con.commit()

    def get_known_nodes(self):
        self.cur.execute("""SELECT id, base_url
                       FROM nodes
                       WHERE id <> ?
                       ORDER BY id ASC""", (self.node_id,))
        return self.cur.fetchall()

    def get_rev_shadow(self, other_node_id, item_id):
        self.cur.execute("""SELECT shadow, rev, other_node_rev
                FROM shadows
                WHERE item = ?
                AND other_node = ?
                ORDER BY rev DESC LIMIT 1""", (item_id, other_node_id,))
        shadow = self.cur.fetchone()
        if shadow is None:
            self._log_debug_trans("shadow doesn't exist. Creating...")
            rev = -1
            other_node_rev = -1
            shadow = ""
            insert = (item_id,
                      other_node_id,
                      rev,
                      other_node_rev,
                      shadow
                      )
            self.cur.execute("""INSERT OR IGNORE INTO shadows
                               (item, other_node, rev, other_node_rev, shadow)
                               VALUES (?,?,?,?,?)""", insert)
        else:
            self._log_debug_trans("shadow exists")
            try:
                rev = shadow['rev']
                other_node_rev = shadow['other_node_rev']
                shadow = shadow['shadow']
            except (TypeError, IndexError) as err:
                log.error(err)
                raise
        return rev, other_node_rev, shadow

    def save_item(self, item_id, new_text):
        self.cur.execute("""INSERT OR REPLACE INTO items
                       (id,
                        text,
                        node)
                       VALUES (?,?,?)""", (item_id, new_text, self.node_id))
        self._log_debug_trans("item {} updated".format(item_id))

    def save_new_shadow(self, other_node_id, item_id, new_text, rev, other_node_rev):
        insert = (item_id,
                  other_node_id,
                  rev,
                  other_node_rev,
                  new_text
                  )
        self.cur.execute("""INSERT OR IGNORE INTO shadows
                           (item, other_node, rev, other_node_rev, shadow)
                           VALUES (?,?,?,?,?)""", insert)
        self._log_debug_trans("shadow {} {} {} saved".format(item_id, other_node_id, rev))

    def enqueue_client_edits(self, other_node_id, item_id, new_text, old_shadow, rev, other_node_rev):
        insert = (
            item_id,
            other_node_id,
            rev,
            other_node_rev,
            create_diff_edits(new_text, old_shadow),  # maybe doing a slow blocking diff inside a transaction is wrong
            create_hash(old_shadow),
            create_hash(new_text),
            )
        self.cur.execute("""INSERT OR IGNORE INTO edits
                           (item, other_node, rev, other_node_rev, edits, old_shadow_adler32, shadow_adler32)
                           VALUES (?,?,?,?,?,?,?)""", insert)
        self._log_debug_trans("edits {} {} {} saved".format(item_id, other_node_id, rev))

    def get_first_queued_edit(self, other_node_id):
        self.cur.execute("""SELECT edits, old_shadow_adler32, shadow_adler32, rev, other_node_rev
                 FROM edits
                 WHERE
                 other_node = ?
                 ORDER BY rev ASC LIMIT 1""", (other_node_id,))
        edit = self.cur.fetchone()
        if not edit:
            self._log_debug_trans("no edits")
        return edit

    def _get_trans_prefix(self):
        if self.con.in_transaction:
            return "[trans-" + str(self._transaction_code) + "] "
        else:
            return ""

    def _log_debug_trans(self, msg):  # FIXME maybe use extra or add a filter in logger
        debug_msg = "{}" + msg
        log.debug(debug_msg.format(self._get_trans_prefix()))

    def start_transaction(self, msg=""):
        self.cur.execute("begin")
        if self.con.in_transaction:
            self._transaction_code = random.randint(0, 1000000)
            edited_msg = ""
            if msg:
                edited_msg = ": " + msg
            self._log_debug_trans("transaction started{}".format(edited_msg))
        else:
            log.error("NOT in_transaction")
            raise Exception

    def end_transaction(self):
        if not self.con.in_transaction:
            log.debug("explicit end requested, but transaction already ended")
        self._log_debug_trans("transaction ending")
        self.cur.execute("commit")
        self.con.commit()
        if self.con.in_transaction:
            self._log_debug_trans("transaction NOT ended")
            raise Exception

    def __init__(self, node_id, db_prefix="", drop_db=False):
        if not node_id:
            raise Exception
        else:
            self.node_id = node_id
            self.db_prefix = db_prefix

        self._transaction_code = None
        self.db_path = ""
        self.get_db_path()
        with sqlite3.connect(self.db_path) as con:
            con.isolation_level = None
            con.row_factory = sqlite3.Row
            self._init_db(con, drop_db)


class AbrimConfig(object):
    def load_config(self):
        name = "Abrim"
        author = "DST"

        if sys.platform == 'darwin':
            config_folder_path = "~/Library/Application Support/{}".format(name, )
        elif sys.platform == 'win32':
            try:
                appdata = os.environ['APPDATA']
                config_folder_path = "{}/{}/{}".format(appdata, author, name, )
            except KeyError:
                log.error("I think this is a Windows OS and %APPDATA% variable is missing")
                raise
        else:
            config_folder_path = "~/.config/{}".format(name, )

        config_folder = Path(config_folder_path)
        config_file_path = config_folder / "abrim_config.ini"

        if config_file_path.exists():
            log.debug("trying to load config from {}".format(config_file_path, ))
            # create node id if it doesn't exist
            # node_id = uuid.uuid4().hex
            raise Exception  # FIXME: add configparser
        else:
            log.debug("no config file, checking environment variable")
            try:
                self.node_id = os.environ['ABRIM_NODE_ID']
            except KeyError:
                log.error("can't locate NODE_ID value")
                raise

    def __init__(self, node_id=None, db_prefix="", drop_db=False):
        if not node_id:
            self.load_config()
        else:
            self.node_id = node_id
        self.db = Db(self.node_id, db_prefix, drop_db)
        self.edit_queue_limit = 50


def create_diff_edits(text, shadow):
    if text == shadow:
        log.debug("both texts are the same...")
        return None
    log.debug("about to diff \"{}\" with \"{}\"".format(shadow, text,))
    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = 1
    diff = diff_obj.diff_main(shadow, text)
    diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
    patch = diff_obj.patch_make(diff)
    if patch:
        return diff_obj.patch_toText(patch)
    else:
        log.debug("no patch results...")
        return None


def create_hash(text):
    adler32 = zlib.adler32(text.encode())
    log.debug("new hash {}".format(adler32))
    return adler32


if __name__ == "__main__":
    pass
