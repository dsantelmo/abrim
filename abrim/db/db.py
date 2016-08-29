#!/usr/bin/env python
import sys
import os
import sqlite3
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename
from abrim.utils import exit_codes


def _get_config_paths(app_name, app_author, default_config_filename='default', default_config_extension='.cfg'):
    default_config_filename = secure_filename(default_config_filename + default_config_extension)
    user_config_filename = secure_filename(app_name + default_config_extension)

    default_config_dir = appdirs.site_config_dir(app_name, app_author)
    default_config_path = os.path.join(
        default_config_dir,
        default_config_filename
    )
    if not os.path.exists(default_config_dir):
        os.makedirs(default_config_dir)
    try:
        print("Opening config at: {0}".format(default_config_path,))
        open(default_config_path, 'a').close()
    except FileNotFoundError:
        print("IOError while opening config file at: {0}".format(default_config_path,))
        sys.exit(exit_codes.EX_OSFILE)


    user_config_dir = appdirs.user_config_dir(app_name, app_author)
    user_config_path = os.path.join(
        user_config_dir,
        user_config_filename
    )
    if not os.path.exists(user_config_dir):
        os.makedirs(user_config_dir)
    try:
        print("Opening config at: {0}".format(user_config_path,))
        open(user_config_path, 'a').close()
    except FileNotFoundError:
        print("IOError while opening config file at: {0}".format(user_config_path,))
        sys.exit(exit_codes.EX_OSFILE)

    return [default_config_path, user_config_path,]


def _load_from_config_files(app, config_paths):
    for config_path in config_paths:
        try:
            app.config.from_pyfile(config_path)
        except IOError:
            print("IOError while opening config file at: {0}".format(config_path,))
            sys.exit(exit_codes.EX_OSFILE)
        except IndentationError:
            print("IndentationError while opening config file at: {0}".format(config_path,))
            sys.exit(exit_codes.EX_DATAERR)

def get_db_path(string_to_format, client_port):
    db_filename = secure_filename(string_to_format.format(client_port))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), db_filename)

def connect_db(db_path):
    rv = sqlite3.connect(db_path)
    rv.row_factory = sqlite3.Row
    return rv