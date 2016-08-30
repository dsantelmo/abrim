#!/usr/bin/env python
import sys
import os
import sqlite3
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename


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


def init_db(app, g, db_path):
    with app.app_context():
        db = get_db(g, db_path)
        with app.open_resource('db\\schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def close_db(g, error):
    """Closes the database again at the end of the request."""
    #print("closing...")
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


# FIXME: delete g and db_path from params...
def get_content_or_shadow(g, db_path, user_id, content=True):
    content_or_shadow = 'shadow'
    if content:
        content_or_shadow = 'content'
    db = get_db(g, db_path)
    select_query = """
                   SELECT {}
                   FROM texts
                   WHERE user_id = ?
                   """.format(content_or_shadow)
    # FIXME logging...
    #print("{0} -- {1}".format(select_query,user_id,))
    cur = db.execute(select_query, (user_id,))
    try:
        result = cur.fetchone()[0]
        # print("--->" + result + "<----")
        return result
    except TypeError:
        #print("__get_{} returned None".format(content_or_shadow))
        return None
    except:
        #print("__get_{} FAILED!!".format(content_or_shadow))
        raise

# FIXME: delete g and db_path from params...
def set_content_or_shadow(g, db_path, user_id, new_value, content=True):
    content_or_shadow = 'shadow'
    if content:
        content_or_shadow = 'content'

    if new_value is None:
        new_value = ""
    try:
        db = get_db(g, db_path)
        insert_query = """
                       INSERT OR IGNORE INTO texts
                       (user_id, {})
                       VALUES (?,?)
                       """.format(content_or_shadow)
        update_query = """
                       UPDATE texts
                       SET {} = ?
                       WHERE user_id = ?
                       """.format(content_or_shadow)
        # FIXME logging...
        # print("{0} -- {1} -- {2}".format(insert_query, user_id, new_value,))
        db.execute(insert_query, (user_id, new_value,))
        # print("{0} -- {1} -- {2}".format(update_query, user_id, new_value))
        db.execute(update_query, (new_value, user_id))
        db.commit()
        return True
    except:
        #print("__set_{} FAILED!!".format(content_or_shadow))
        raise
