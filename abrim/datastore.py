import os
import random
import sqlite3
import sys
import uuid

from util import get_log

log = get_log(full_debug=False)


class DataStore(object):

    # MAINTENANCE
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
        # log.debug(self.db_path)

    def drop_db(self):
        self.cur.execute("""SELECT name FROM sqlite_master WHERE type = 'table';
            """)

        drop_tables = """"""
        for table in self.cur.fetchall():
            drop_tables = drop_tables + """DROP TABLE IF EXISTS """ + table['name'] + """; """

        self.cur.executescript(drop_tables)

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
            crc INTEGER NOT NULL,
            FOREIGN KEY(node) REFERENCES nodes(id)
            );

           CREATE TABLE IF NOT EXISTS shadows
           (item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            n_rev INTEGER NOT NULL,
            m_rev INTEGER NOT NULL,
            shadow TEXT,
            crc INTEGER NOT NULL,
            PRIMARY KEY(item, other_node, n_rev, m_rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );

           CREATE TABLE IF NOT EXISTS edits
           (
            item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            n_rev INTEGER NOT NULL,
            m_rev INTEGER NOT NULL,
            edits TEXT,
            old_shadow_adler32 TEXT,
            shadow_adler32 TEXT,
            PRIMARY KEY(item, other_node, n_rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );

           CREATE TABLE IF NOT EXISTS edits_archive
           (
            item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            n_rev INTEGER NOT NULL,
            m_rev INTEGER NOT NULL,
            edits TEXT,
            old_shadow_adler32 TEXT,
            shadow_adler32 TEXT,
            PRIMARY KEY(item, other_node, n_rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );

           CREATE TABLE IF NOT EXISTS patches
           (
            item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            n_rev INTEGER NOT NULL,
            m_rev INTEGER NOT NULL,
            patches TEXT,
            old_crc INTEGER NOT NULL,
            new_crc INTEGER NOT NULL,
            PRIMARY KEY(item, other_node, n_rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );

           CREATE TABLE IF NOT EXISTS patches_archive
           (
            item TEXT NOT NULL,
            other_node TEXT NOT NULL,
            n_rev INTEGER NOT NULL,
            m_rev INTEGER NOT NULL,
            patches TEXT,
            old_crc INTEGER NOT NULL,
            new_crc INTEGER NOT NULL,
            PRIMARY KEY(item, other_node, n_rev),
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(other_node) REFERENCES nodes(id)
            );
            """)

        self.con.commit()

        self.start_transaction()  # init the DB
        try:
            self.cur.execute("""SELECT id FROM nodes
                           WHERE base_url IS NULL""")
            node_uuid = self.cur.fetchone()
            if node_uuid is None:
                node_uuid = uuid.uuid4().hex
                insert = (node_uuid,
                          None
                          )
                self.cur.execute("""INSERT OR IGNORE INTO nodes
                               (id,
                                base_url)
                               VALUES (?,?)""", insert)
            # self._log_debug_trans("_init_db done")
            self.end_transaction(suppress_msg=True)
        except Exception as err:
            self._log_debug_trans("rollback in _init_db")
            log.error(err)
            self.cur.execute("rollback")
            raise

    # TRANSACTION

    def _get_trans_prefix(self):
        if self.con.in_transaction:
            return "[trans-" + str(self._transaction_code) + "] "
        else:
            return ""

    # TODO: add more hints
    def _log_debug_trans(self, msg: str):  # FIXME maybe use extra or add a filter in logger
        debug_msg = "{}" + str(msg)
        log.debug(debug_msg.format(self._get_trans_prefix()))

    def start_transaction(self, msg=None):
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

    def end_transaction(self, suppress_msg=False):
        if not self.con.in_transaction:
            log.debug("explicit end requested, but transaction already ended or db is missing")
        else:
            if not suppress_msg:
                self._log_debug_trans("transaction ending")
            self.cur.execute("commit")
            self.con.commit()
        if self.con.in_transaction:
            self._log_debug_trans("transaction NOT ended")
            raise Exception

    def check_transaction(self):
        if self.con.in_transaction:
            return True
        else:
            return False

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

    def sql_debug_trace(self, enable: bool):
        callb = None
        if enable:
            callb = log.debug
        self.con.set_trace_callback(callb)

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

    # NODES

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

    # REV AND SHADOW

    def get_latest_rev_shadow(self, other_node_id, item_id):
        self.cur.execute("""SELECT shadow, n_rev, m_rev
                FROM shadows
                WHERE item = ?
                AND other_node = ?
                ORDER BY n_rev DESC LIMIT 1""", (item_id, other_node_id,))
        shadow = self.cur.fetchone()

        if shadow is None:
            self._log_debug_trans("shadow doesn't exist")
            n_rev = -1
            m_rev = 0
            shadow = ""
            return n_rev, m_rev, shadow

        try:
            return shadow['n_rev'], shadow['m_rev'], shadow['shadow']
        except (TypeError, IndexError) as err:
            log.error(err)
            raise

    def get_shadow(self, item, other_node_id, n_rev, m_rev):
        # if n_rev == 0 and m_rev == 0:
        #    self._log_debug_trans("n_revs 0 - 0, assuming there is no shadow")
        #    return None
        self.cur.execute("""SELECT shadow
                 FROM shadows
                 WHERE
                 item = ? AND
                 other_node = ? AND
                 n_rev = ? AND
                 m_rev = ?
                 LIMIT 1""", (item, other_node_id, n_rev, m_rev))
        shadow_row = self.cur.fetchone()
        if not shadow_row:
            self._log_debug_trans("no shadow")
            return False, None
        else:
            return True, shadow_row["shadow"]

    def get_latest_revs(self, item, other_node_id):
        self.cur.execute("""SELECT n_rev, m_rev
                 FROM shadows
                 WHERE
                 item = ? AND
                 other_node = ?
                 ORDER BY n_rev DESC LIMIT 1""", (item, other_node_id,))
        revs_row = self.cur.fetchone()
        if not revs_row:
            self._log_debug_trans("no revs, defaulting to 0 - 0")
            return 0, 0
        else:
            return revs_row["n_rev"], revs_row["m_rev"]

    def save_new_shadow(self, other_node_id, item_id, new_text, n_rev, m_rev, crc):
        self._log_debug_trans("about to save shadow: {} {} {}".format(item_id, other_node_id, n_rev))
        insert = (item_id,
                  other_node_id,
                  n_rev,
                  m_rev,
                  new_text,
                  crc
                  )
        self.cur.execute("""INSERT OR REPLACE INTO shadows
                           (item, other_node, n_rev, m_rev, shadow, crc)
                           VALUES (?,?,?,?,?,?)""", insert)

    # ITEM

    def save_item(self, item_id, new_text, text_crc):
        self._log_debug_trans("about to save item: {} {}".format(item_id, text_crc))
        self.cur.execute("""INSERT OR REPLACE INTO items
                       (id,
                        text,
                        node,
                        crc)
                       VALUES (?,?,?,?)""", (item_id, new_text, self.node_id, text_crc))
        self._log_debug_trans("item {} updated".format(item_id))

    def get_item(self, item_id):
        self.cur.execute("""SELECT text, crc
                  FROM items
                  WHERE
                  id = ? AND
                  node = ?
                  LIMIT 1""", (item_id, self.node_id))
        item_row = self.cur.fetchone()
        if not item_row:
            self._log_debug_trans("no item found for {}".format(item_id, ))
            return False, None, None
        else:
            return True, item_row["text"], item_row["crc"]

    def get_items(self):
        self.cur.execute("""SELECT id, node, crc 
                            FROM items
                            ORDER BY id, node""")
        items = []
        for item in self.cur.fetchall():
            items.append({"id": item["id"], "node": item["node"], "crc": item["crc"], })
        return items

    # EDITS

    def enqueue_client_edits(self, other_node_id, item_id, diffs, old_hash, new_hash, n_rev, m_rev):
        insert = (
            item_id,
            other_node_id,
            n_rev,
            m_rev,
            diffs,
            old_hash,
            new_hash,
        )
        try:
            self.cur.execute("""INSERT INTO edits
                               (item, other_node, n_rev, m_rev, edits, old_shadow_adler32, shadow_adler32)
                               VALUES (?,?,?,?,?,?,?)""", insert)
        except sqlite3.InterfaceError as err:
            self._log_debug_trans("ERROR AT INSERT VALUES: {}, {}, {}, {}, {}, {}, {}".format(
                item_id,
                other_node_id,
                n_rev,
                m_rev,
                diffs,
                old_hash,
                new_hash,
            ))
            raise

        self._log_debug_trans("edits {} {} {} saved".format(item_id, other_node_id, n_rev))

    def get_first_queued_edit(self, other_node_id):
        self.cur.execute("""SELECT rowid, *
                 FROM edits
                 WHERE
                 other_node = ?
                 ORDER BY n_rev ASC LIMIT 1""", (other_node_id,))
        edit_row = self.cur.fetchone()
        if not edit_row:
            return None, None
        else:
            log.debug("----------------------------------------------------------")
            self._log_debug_trans("got edits")
            edit_rowid = edit_row["rowid"]
            edit = dict(edit_row)
            return edit_rowid, edit

    def archive_edit(self, edit_rowid):
        self.cur.execute("""INSERT INTO edits_archive
                           SELECT * FROM edits
                           WHERE rowid=?""", (edit_rowid,))
        self._log_debug_trans("edit rowid {} archived".format(edit_rowid))

    def delete_edit(self, edit_rowid):
        self.cur.execute("""DELETE FROM edits
                           WHERE rowid=?""", (edit_rowid,))
        self._log_debug_trans("edit rowid {} deleted".format(edit_rowid))


    # PATCHES

    def save_new_patches(self, other_node_id, item_id, patches, n_rev, m_rev, old_crc, new_crc):
        self._log_debug_trans("about to save patch: {} {} {}".format(item_id, other_node_id, n_rev))
        insert = (item_id,
                  other_node_id,
                  n_rev,
                  m_rev,
                  patches,
                  old_crc,
                  new_crc
                  )
        self.cur.execute("""INSERT OR REPLACE INTO patches
                           (item, other_node, n_rev, m_rev, patches, old_crc, new_crc)
                           VALUES (?,?,?,?,?,?,?)""", insert)

    def check_if_patch_done(self, other_node_id, item_id, n_rev, m_rev):
        self.cur.execute("""SELECT n_rev, m_rev
                 FROM patches_archive
                 WHERE
                 item = ? AND
                 other_node = ? AND
                 n_rev = ? AND
                 m_rev = ? 
                 LIMIT 1""", (item_id, other_node_id, n_rev, m_rev))
        patch_row = self.cur.fetchone()
        if not patch_row:
            self._log_debug_trans("server has still not applied the patch")
            return False
        else:
            self._log_debug_trans("server has correctly applied the patch")
            return True

    def get_nodes_from_patches(self):
        self.cur.execute("""SELECT DISTINCT other_node
                            FROM patches
                            GROUP BY other_node
                            ORDER BY rowid""")
        nodes = self.cur.fetchall()
        node_ids = []
        if nodes:
            for node in nodes:
                node_ids.append(node["other_node"])
        return node_ids

    def check_first_patch(self, other_node):
        self.cur.execute("""SELECT item, other_node, n_rev, m_rev, patches, old_crc, new_crc
                            FROM patches
                            WHERE other_node = ?
                            ORDER BY m_rev, n_rev, rowid ASC
                            LIMIT 1""", (other_node,))
        patch_row = self.cur.fetchone()
        if not patch_row:
            return None
        else:
            item = patch_row["item"]
            other_node = patch_row["other_node"]
            n_rev = patch_row["n_rev"]
            m_rev = patch_row["m_rev"]
            patches = patch_row["patches"]
            old_crc = patch_row["old_crc"]
            new_crc = patch_row["new_crc"]
            return item, other_node, n_rev, m_rev, patches, old_crc, new_crc

    def archive_patch(self, item, other_node, n_rev):
        self.cur.execute("""INSERT INTO patches_archive
                           SELECT * FROM patches
                           WHERE
                           item = ? AND
                           other_node = ? AND
                           n_rev = ?
                           """, (item, other_node, n_rev,))
        self._log_debug_trans("edit rowid {} {} {} archived".format(item, other_node, n_rev))

    def delete_patch(self, item, other_node, n_rev):
        self.cur.execute("""DELETE FROM patches
                           WHERE
                           item = ? AND
                           other_node = ? AND
                           n_rev = ?""", (item, other_node, n_rev,))
        self._log_debug_trans("edit rowid {} {} {} deleted".format(item, other_node, n_rev))
