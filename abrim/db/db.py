#!/usr/bin/env python
import sys
import os
import sqlite3
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename

CONTENT=True
SHADOW=False


def get_db_path(string_to_format, client_port):
    db_filename = secure_filename(string_to_format.format(client_port))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), db_filename)


def connect_db(db_path):
    """Connects to the specific database."""
    rv = sqlite3.connect(db_path)
    rv.row_factory = sqlite3.Row
    return rv


def get_db(g, db_path):
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db(db_path)
    return g.sqlite_db


def init_db(app, g, db_path, schema_path):
    with app.app_context():
        db = get_db(g, db_path)
        with app.open_resource(schema_path, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def close_db(g, error):
    """Closes the database again at the end of the request."""
    # print("closing...")
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


# FIXME: delete g and db_path from params...
def get_content_or_shadow(g, db_path, item_id, node_id, user_id, content=True):
    # print("------>" + item_id + " - " + node_id)
    content_or_shadow = 'shadow'
    if content:
        content_or_shadow = 'content'
    db = get_db(g, db_path)
    select_query = """
                   SELECT {}
                   FROM items
                   WHERE item_id = ? and node_id = ?
                   """.format(content_or_shadow)
    # FIXME logging...
    # print("{0} -- {1}".format(select_query,text_id,))
    cur = db.execute(select_query, (item_id, node_id, ))
    try:
        result = cur.fetchone()[0]
        return result
    except TypeError:
        # print("__get_{} returned None".format(content_or_shadow))
        return None
    except:
        # print("__get_{} FAILED!!".format(content_or_shadow))
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
        # FIXME logging...
        # print("{0} -- {1} -- {2} -- {3}".format(insert_query, text_id, user_id, new_value,))
        db.execute(insert_query, (item_id, node_id, user_id, new_value,))
        # print("{0} -- {1} -- {2} -- {3}".format(update_query, new_value, text_id, user_id,))
        db.execute(update_query, (new_value, item_id, node_id, user_id))
        db.commit()
        return True
    except:
        # print("__set_{} FAILED!!".format(content_or_shadow))
        raise


def create_item(g, db_path, node_id, user_id, content):
    try:
        db = get_db(g, db_path)
        insert_query = """
                       INSERT OR IGNORE INTO items
                       (node_id, user_id, content)
                       VALUES (?, ?, ?, ?)
                       """
        cur = db.execute(insert_query, (node_id, user_id, content,))
        item_id = cur.lastrowid
        db.commit()
        return item_id
    except:
        # print("__set_{} FAILED!!".format(content_or_shadow))
        raise


def get_all_tables(g, db_path):
    db = get_db(g, db_path)
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'sqlite_sequence';")
    # FIXME SANITIZE THIS! SQL injections...
    return [table_name[0] for table_name in cur.fetchall()]


def get_table_contents(g, db_path, table_names):
    db = get_db(g, db_path)
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
    # FIXME logging...
    # print("{0} -- {1}".format(select_query,text_id,))
    print(select_query, (user_id, node_id, ))
    cur = db.execute(select_query, (user_id, node_id, ))
    result = []
    try:
        for row in cur.fetchall():
            result.append({"item_id": row["item_id"], "content": row["content"], "shadow": row["shadow"]})
        # print("--->" + result + "<----")
        return result
    except TypeError:
        # print("__get_{} returned None".format(content_or_shadow))
        return []
    except:
        # print("__get_{} FAILED!!".format(content_or_shadow))
        raise
    return result