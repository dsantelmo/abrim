#!/usr/bin/env python

import traceback
import time
from flask import Flask, render_template
import flask_login
from abrim.config import Config
from abrim.util import get_log, fragile_patch_text, resp, check_fields_in_dict, check_crc, get_crc, create_diff_edits, \
                       create_hash, args_init

log = get_log(full_debug=False)

app = Flask(__name__)


def __end():
    # db.close_db()
    pass


@app.before_request
def before_request():
    # db.prepare_db_path(app.config['DB_PATH'])
    pass


@app.teardown_request
def teardown_request(exception):
    __end()


@app.route('/', methods=['GET'])
def _root():
    if not flask_login.current_user.is_authenticated:
         return render_template("login.html")
    return render_template('client.html')



if __name__ == "__main__":  # pragma: no cover
    log.info("ui started")
    node_id, client_port = args_init()
    config = Config(node_id=node_id)
    # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    # app.run(host='0.0.0.0', port=client_port)
    # for pycharm debugging

    login_manager = flask_login.LoginManager()
    login_manager.init_app(app)

    app.run(host='0.0.0.0', port=client_port, debug=True, use_debugger=False, use_reloader=False)
    __end()
