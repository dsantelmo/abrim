#!/usr/bin/env python
import sys
import os
import sqlite3
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename

import logging
log = logging.getLogger()

CONTENT=True
SHADOW=False


def get_db_path(string_to_format, client_port):
    db_filename = secure_filename(string_to_format.format(client_port))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), db_filename)


def __connect_db(db_path):
    """Connects to the specific database."""
    rv = sqlite3.connect(db_path)
    rv.row_factory = sqlite3.Row
    return rv


def get_db(g, db_path):
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = __connect_db(db_path)
    return g.sqlite_db


def init_db(app, g, db_path, schema_path):
    with app.app_context():
        db = get_db(g, db_path)
        with app.open_resource(schema_path, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def close_db(g):
    """Closes the database again at the end of the request."""
    log.debug("closing DB")
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


# FIXME: delete g and db_path from params...
def get_content_or_shadow(g, db_path, item_id, node_id, user_id, content=True):
    content_or_shadow = 'shadow'
    if content:
        log.debug("get_content_or_shadow -> content:" + item_id + " - " + node_id)
        content_or_shadow = 'content'
    else:
        log.debug("get_content_or_shadow -> shadow:" + item_id + " - " + node_id)

    db = get_db(g, db_path)
    select_query = """
SELECT {}
FROM items
WHERE item_id = ? and node_id = ?
""".format(content_or_shadow)
    where_items = (item_id, node_id, )
    log.debug("get_content_or_shadow, SELECT: {0} -- {1}".format(select_query.replace('\n', ' '),where_items,))
    cur = db.execute(select_query, where_items)
    try:
        result = cur.fetchone()[0]
        return result
    except TypeError:
        log.debug("get_content_or_shadow returned None")
        return None
    except:
        log.error("get_content_or_shadow FAILED!!")
        raise

# FIXME: delete g and db_path from params...
def set_content_or_shadow(g, db_path, item_id, node_id, user_id, new_value, content=True):
    content_or_shadow = 'shadow'
    if content:
        content_or_shadow = 'content'

    if new_value is None:
        new_value = ""
    try:
        db = get_db(g, db_path)
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


def create_item(g, app, item_id, node_id, user_id, content):
    try:
        db = get_db(g, app.config['DB_PATH'])
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


def get_all_tables(g, app):
    db = get_db(g, app.config['DB_PATH'])
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'sqlite_sequence';")
    # FIXME SANITIZE THIS! SQL injections...
    return [table_name[0] for table_name in cur.fetchall()]


def get_table_contents(g, app, table_names):
    db = get_db(g, app.config['DB_PATH'])
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


def get_all_user_content(g, db_path, user_id, node_id):
    result = []
    db = get_db(g, db_path)
    select_query = """
SELECT item_id, content, shadow
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


def get_user_node_items(g, app, user_id, node_id):
    return get_all_user_content(g, app.config['DB_PATH'], user_id, node_id)

def get_content(g, app, user_id, node_id, item_id):
    return get_content_or_shadow(g, app.config['DB_PATH'], item_id, node_id, user_id, CONTENT)


def get_shadow(g, app, user_id, node_id, item_id):
    return get_content_or_shadow(g, app.config['DB_PATH'], item_id, node_id, user_id, SHADOW)


def set_content(g, app, user_id, node_id, item_id, value):
    return set_content_or_shadow(g, app.config['DB_PATH'], item_id, node_id, user_id, value, CONTENT)


def set_shadow(g, app, user_id, node_id, item_id, value):
    return set_content_or_shadow(g, app.config['DB_PATH'], item_id, node_id, user_id, value, SHADOW)


def set_server_text(g, app, text):
    set_content(g, app, app.config['NODE_ID'], text)
    #with closing(shelve.open(temp_server_file_name)) as d:
    #    d['server_text'] = text