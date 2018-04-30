#!/usr/bin/env python

import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import logging
import os
import zlib
import hashlib
from pathlib import Path
import sqlite3


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

    LOGGING_LEVELS = {'critical': logging.CRITICAL,
                      'error': logging.ERROR,
                      'warning': logging.WARNING,
                      'info': logging.INFO,
                      'debug': logging.DEBUG}
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
            
            """)

        self.con.commit()

        self.start_transaction()
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
            self.end_transaction()
        except Exception as err:
            log.error("rollback in _init_db")
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
            log.debug("shadow doesn't exist. Creating...")
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
            log.debug("shadow exists")
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

    def enqueue_client_edits(self, other_node_id, item_id, new_text, old_shadow, rev, other_node_rev):
        #_enqueue_client_edits(item_ref, new_text, old_shadow, shadow_client_rev, shadow_server_rev, transaction, node_id):
        return True


        try:
            item_data, queue_data, shadow_data = prepare_data(new_text, old_shadow, old_shadow_adler32, shadow_adler32,
                                                              shadow_client_rev, shadow_server_rev, text_patches)

            log.debug("creating shadow, queue and saving item for node {}".format(node_id))
            shadow_ref = _get_shadow_revs_ref(item_ref, node_id).document(str(shadow_client_rev))
            queue_ref = get_queue_1_revs_ref(item_ref, node_id).document(str(shadow_client_rev))
            transaction.set(shadow_ref, shadow_data)
            transaction.set(queue_ref, queue_data)
            transaction.set(item_ref, item_data)

            log.debug('About to commit transaction...')
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            log.error("Connection error to Firestore")
            return False
        log.info('New update saved')
        return True

    def start_transaction(self):
        self.cur.execute("begin")
        if self.con.in_transaction:
            log.debug("transaction started")
        else:
            log.error("NOT in_transaction")
            raise Exception

    def end_transaction(self):
        if not self.con.in_transaction:
            log.debug("explicit end requested, but transaction already ended")
        self.cur.execute("commit")
        self.con.commit()
        if not self.con.in_transaction:
            log.debug("transaction ended")
        else:
            log.error("transaction NOT ended")
            raise Exception


    def __init__(self, node_id, db_prefix="", drop_db=False):
        if not node_id:
            raise Exception
        else:
            self.node_id = node_id
            self.db_prefix = db_prefix

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


def create_diff_edits(text, shadow):
    log.debug("about to diff \"{}\" with \"{}\"".format(shadow,text,))
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
    # shadow_sha512 = hashlib.sha512(new_text.encode()).hexdigest()
    return adler32

if __name__ == "__main__":
    pass
