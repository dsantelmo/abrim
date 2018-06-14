import os
import random
import sqlite3
import sys

from util import get_log, create_diff_edits, create_hash

log = get_log(full_debug=False)


class DataStore(object):
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
        log.debug(self.db_path)

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
           (
            item TEXT NOT NULL,
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

           CREATE TABLE IF NOT EXISTS edits_archive
           (
            item TEXT NOT NULL,
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
        self.cur.execute("""SELECT rowid, *
                 FROM edits
                 WHERE
                 other_node = ?
                 ORDER BY rev ASC LIMIT 1""", (other_node_id,))
        edit_row = self.cur.fetchone()
        if not edit_row:
            self._log_debug_trans("no edits")
            return None, None
        else:
            edit_rowid = edit_row["rowid"]
            edit = dict(edit_row)
            return edit_rowid, edit

    def archive_edit(self, edit_rowid):
        self.cur.execute("""INSERT OR IGNORE INTO edits_archive
                           SELECT * FROM edits
                           WHERE rowid=?""", (edit_rowid,))
        self._log_debug_trans("edit rowid {} archived".format(edit_rowid))

    def delete_edit(self, edit_rowid):
        self.cur.execute("""DELETE FROM edits
                           WHERE rowid=?""", (edit_rowid,))
        self._log_debug_trans("edit rowid {} deleted".format(edit_rowid))

    def get_revs(self, item, other_node_id):
        self.cur.execute("""SELECT rev, other_node_rev
                 FROM shadows
                 WHERE
                 item = ? AND
                 other_node = ?
                 ORDER BY rev ASC LIMIT 1""", (item, other_node_id,))
        revs_row = self.cur.fetchone()
        if not revs_row:
            self._log_debug_trans("no revs, defaulting to 0 - 0")
            return 0, 0
        else:
            return revs_row["rev"], revs_row["other_node"]

    def get_shadow(self, item, other_node_id, rev, other_node_rev):
        if rev == 0 and other_node_rev == 0:
            self._log_debug_trans("revs 0 - 0, assuming there is no shadow")
            return None
        self.cur.execute("""SELECT shadow
                 FROM shadows
                 WHERE
                 item = ? AND
                 other_node = ? AND
                 rev = ? AND
                 other_node_rev = ?
                 LIMIT 1""", (item, other_node_id, rev, other_node_rev))
        shadow_row = self.cur.fetchone()
        if not shadow_row:
            self._log_debug_trans("no shadow")
            return None
        else:
            return shadow_row["shadow"]

    def _get_trans_prefix(self):
        if self.con.in_transaction:
            return "[trans-" + str(self._transaction_code) + "] "
        else:
            return ""

    def _log_debug_trans(self, msg):  # FIXME maybe use extra or add a filter in logger
        debug_msg = "{}" + str(msg)
        log.debug(debug_msg.format(self._get_trans_prefix()))

    def start_transaction(self, msg=""):
        if self.con.in_transaction:
            log.error("cannot start a transaction within a transaction. Rolling back!!")
            self.cur.execute("rollback")
            raise Exception

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

    def rollback_transaction(self, msg=""):
        if self.con.in_transaction:
            self._log_debug_trans("explicitly rolling back this transaction.")
            self.cur.execute("rollback")
        else:
            log.warning("tried to rollback a transaction but there was none!!")
        if self.con.in_transaction:
            self._log_debug_trans("still in transaction...")
            log.error("rollback failed!")
            raise Exception
        else:
            log.debug("transaction rolled back OK")

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