#!/usr/bin/env python
import sys
import os
import sqlite3
from flask import g
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename

import logging
log = logging.getLogger()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_db_path(string_to_format, client_port):
    try:
        db_filename = secure_filename(string_to_format.format(client_port))
    except ValueError:
        db_filename = 'abrimsync-TEST.sqlite_test'
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), db_filename)


def prepare_db_path(db_path):
    """Saves the DB path to g.db_path.
    """
    if not hasattr(g, 'db_path'):
        g.db_path = db_path


def __connect_db(db_path):
    """Connects to the specific database."""
    rv = sqlite3.connect(db_path)
    rv.row_factory = dict_factory
    return rv


def __get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = __connect_db(g.db_path)
    return g.sqlite_db


def init_db(app):
    with app.app_context():
        db = __connect_db(app.config['DB_PATH'])
        with app.open_resource(app.config['DB_SCHEMA_PATH'], mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def close_db():
    """Closes the database again at the end of the request."""
    log.debug("closing DB")
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def set_content_or_shadow(item_id, node_id, user_id, new_value, content=True):
    content_or_shadow = 'shadow'
    if content:
        content_or_shadow = 'content'

    if new_value is None:
        new_value = ""
    try:
        db = __get_db()
        insert_query = """
INSERT OR IGNORE INTO items
(item_id, node_id, user_id, {})
VALUES (?, ?, ?, ?)
""".format(content_or_shadow)

        update_query = """
UPDATE items
SET {} = ?
WHERE item_id = ? AND node_id = ? AND user_id = ?
""".format(content_or_shadow)

        where_items = (item_id, node_id, user_id, new_value,)
        log.debug("set_content_or_shadow, INSERT: {0} -- {1}".format(insert_query.replace('\n', ' '),where_items,))
        db.execute(insert_query, where_items)

        where_items = (new_value, item_id, node_id, user_id,)
        log.debug("set_content_or_shadow, UPDATE: {0} -- {1}".format(update_query.replace('\n', ' '),where_items,))
        db.execute(update_query, where_items)
        db.commit()
        return True
    except:
        log.error("set_content_or_shadow FAILED!!")
        raise


def create_item(item_id, node_id, user_id, content):
    try:
        db = __get_db()
        insert_query = """
INSERT --OR IGNORE
INTO items
(item_id, node_id, user_id, content)
VALUES (?, ?, ?, ?)
"""

        where_items = (item_id, node_id, user_id, content,)
        log.debug("create_item, INSERT: {0} -- {1}".format(insert_query.replace('\n', ' '),where_items,))
        cur = db.execute(insert_query, where_items)
        #item_id = cur.lastrowid
        db.commit()
        return True
    except sqlite3.IntegrityError:
        log.debug("create_item returned False")
        return False
    except:
        log.error("create_item FAILED!!")
        raise


def get_all_tables():
    db = __get_db()
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'sqlite_sequence';")
    # FIXME SANITIZE THIS! SQL injections...
    return [table_name[0] for table_name in cur.fetchall()]


def get_table_contents(table_names):
    db = __get_db()
    contents = []
    for table_name in table_names:
        cur = db.execute("SELECT * FROM {}".format(table_name))
        # FIXME SANITIZE THIS! SQL injections...
        table_contents = []
        table_contents.append(table_name)
        table_contents.append([desc[0] for desc in cur.description])
        table_contents.append(cur.fetchall())
        contents.append(table_contents)
    return contents


def get_all_user_content(user_id, node_id):
    result = []
    db = __get_db()
    select_query = """
SELECT item_id, content
FROM items
WHERE user_id = ? and node_id = ?
"""
    where_items = (user_id, node_id, )
    log.debug("get_all_user_content, SELECT: {0} -- {1}".format(select_query.replace('\n', ' '),where_items,))
    cur = db.execute(select_query, where_items)
    result = []
    try:
        rows = cur.fetchall()
        if rows:
            for row in rows:
                try:
                    result_item_id = row[0]
                except IndexError:
                    result_item_id = None
                try:
                    result_content = row[1]
                except IndexError:
                    result_content = None
                try:
                    result_shadow = row[2]
                except IndexError:
                    result_shadow = None
                result_row = { 'item_id': result_item_id, 'content': result_content, 'shadow': result_shadow}
                result.append(result_row)
                log.debug("get_all_user_content - results: " + str(result_row))
        return result
    except TypeError:
        log.debug("get_all_user_content returned None")
        return []
    except:
        log.error("get_all_user_content FAILED!!")
        raise
    return result


def get_user_node_items(user_id, node_id):
    return get_all_user_content(user_id, node_id)

def get_content(user_id, node_id, item_id):
    log.debug("get_content " + user_id + " - " + item_id + " - " + node_id)
    db = __get_db()
    select_query = """
SELECT content
FROM items
WHERE user_id = ? and item_id = ? and node_id = ?
"""
    where_items = (user_id, item_id, node_id, )
    log.debug("get_content, SELECT: {0} -- {1}".format(select_query.replace('\n', ' '),where_items,))
    cur = db.execute(select_query, where_items)
    try:
        result = cur.fetchone()['content']
        return result
    except TypeError:
        log.debug("get_content returned None")
        return None
    except:
        log.error("get_content FAILED!!")
        raise


def get_shadow(user_id, node_id, item_id):
    log.debug("get_shadow " + user_id + " - " + item_id + " - " + node_id)
    db = __get_db()
    select_query = """
SELECT shadow_id, shadow, client_ver, server_ver
FROM shadows
WHERE user_id = ? and item_id = ? and node_id = ?
"""
    where_items = (user_id, item_id, node_id, )
    log.debug("get_shadow, SELECT: {0} -- {1}".format(select_query.replace('\n', ' '),where_items,))
    cur = db.execute(select_query, where_items)
    try:
        results = cur.fetchone()
        return results
    except TypeError:
        log.debug("get_shadow returned None")
        return None
    except:
        log.error("get_shadow FAILED!!")
        raise


def set_content(user_id, node_id, item_id, value):
    return set_content_or_shadow(item_id, node_id, user_id, value, True)


def create_shadow(user_id, node_id, item_id, value):
    try:
        db = __get_db()
        insert_query = """
INSERT INTO shadows
(shadow, client_ver, server_ver, item_id, user_id, node_id)
VALUES (?, 0, 0, ?, ?, ?)
"""
        where_items = (value, item_id, user_id, node_id,)
        log.debug("set_shadow, INSERT: {0} -- {1}".format(insert_query.replace('\n', ' '),where_items,))
        cur = db.cursor()
        cur.execute(insert_query, where_items)
        shadow_id = cur.lastrowid
        db.commit()
        return shadow_id
    except:
        log.error("set_shadow FAILED!!")
        raise


def set_server_text(text):
    set_content(text)


def save_edit(user_id, node_id, item_id, text_patches, client_ver, server_ver):
    try:
        db = __get_db()
        insert_query = """
    INSERT INTO edits
    (edit, client_ver, server_ver, item_id, user_id, node_id)
    VALUES (?, ?, ?, ?, ?, ?)
    """
        where_items = (text_patches, client_ver, server_ver, item_id, user_id, node_id,)
        log.debug("save_edit, INSERT: {0} -- {1}".format(insert_query.replace('\n', ' '), where_items, ))
        cur = db.cursor()
        cur.execute(insert_query, where_items)
        edit_id = cur.lastrowid
        db.commit()
        return edit_id
    except:
        log.error("save_edit FAILED!!")
        raise
