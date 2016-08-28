#!/usr/bin/env python
import sys
import os
import appdirs
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils.common import secure_filename
from abrim.utils import exit_codes

def load(app):
    default_cfg_filename = secure_filename('default.cfg')
    user_cfg_filename = secure_filename(app.config['APP_NAME'] + '.cfg')

    default_cfg_dir = appdirs.site_config_dir(app.config['APP_NAME'], app.config['APP_AUTHOR'])
    default_cfg_path = os.path.join(
        default_cfg_dir,
        default_cfg_filename
    )
    if not os.path.exists(default_cfg_dir):
        os.makedirs(default_cfg_dir)
    try:
        print("Opening config at: {0}".format(default_cfg_path,))
        open(default_cfg_path, 'a').close()
    except FileNotFoundError:
        print("IOError while opening config file at: {0}".format(default_cfg_path,))
        sys.exit(exit_codes.EX_OSFILE)
    try:
        app.config.from_pyfile(default_cfg_path)
    except IOError:
        print("IOError while opening config file at: {0}".format(default_cfg_path,))
        sys.exit(exit_codes.EX_OSFILE)

    user_cfg_dir = appdirs.user_config_dir(app.config['APP_NAME'], app.config['APP_AUTHOR'])
    user_cfg_path = os.path.join(
        user_cfg_dir,
        user_cfg_filename
    )
    if not os.path.exists(user_cfg_dir):
        os.makedirs(user_cfg_dir)
    try:
        print("Opening config at: {0}".format(user_cfg_path,))
        open(user_cfg_path, 'a').close()
    except FileNotFoundError:
        print("IOError while opening config file at: {0}".format(default_cfg_path,))
        sys.exit(exit_codes.EX_OSFILE)
    try:
        app.config.from_pyfile(user_cfg_path)
    except IOError:
        print("IOError while opening config file at: {0}".format(user_cfg_path,))
        sys.exit(exit_codes.EX_OSFILE)
