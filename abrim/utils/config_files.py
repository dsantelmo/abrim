#!/usr/bin/env python
import sys
import os
import appdirs
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
        # FIXME: define logging -> print("Opening config at: {0}".format(default_config_path,))
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
        # FIXME: define logging -> print("Opening config at: {0}".format(user_config_path,))
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


def _show_secret_key_warning(config_paths):
    if config_paths[0]:
        print("""===============================================================================
WARNING! No SECRET_KEY has been set in config files.
  Sessions will be lost every time this server is restarted
  Edit at least one of the config files:""")
        print("""  * {}""".format(config_paths[0]))
        for config_path in config_paths[1:]:
            print("""  or:
  * {}""".format(config_path))
        print("""  Add a line with SECRET_KEY = ' and a long random key:
SECRET_KEY = '""" + r"""?\xbf,\xb4\x8d...')
===============================================================================""")


def load_app_config(app):
    # load random secret_key in case none is loaded with the config files
    default_secret_key = os.urandom(24)
    app.secret_key = default_secret_key

    # load config from different sources:
    #app.config.from_object(__name__)
    config_paths = _get_config_paths(app.config['APP_NAME'], app.config['APP_AUTHOR'])
    _load_from_config_files(app, config_paths)

    if app.secret_key == default_secret_key:
        _show_secret_key_warning(config_paths)