#!/usr/bin/env python

import traceback
import time
from flask import Flask, request, abort, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from abrim.config import Config
from abrim.util import get_log, fragile_patch_text, resp, check_fields_in_dict, check_crc, get_crc, create_diff_edits, \
                       create_hash, args_init

log = get_log(full_debug=False)

app = Flask(__name__)

app.secret_key = "CHANGE_ME"  # TODO: manage this in admin UI

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "_login"

class User(UserMixin):

    def __init__(self, id):
        self.id = id
        self.name = "user" + str(id)
        self.password = self.name + "_secret"

    def __repr__(self):
        return "%d/%s/%s" % (self.id, self.name, self.password)

users = [User(id) for id in range(1, 21)]


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
    if not current_user.is_authenticated:
        return redirect(url_for('_login'))
    return render_template('client.html')


@app.route('/login', methods=['GET', 'POST'])
def _login():
    if  current_user.is_authenticated:
        return redirect(url_for('_root'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if password == username + "_secret":
            id = username.split('user')[1]
            user = User(id)
            login_user(user)
            return redirect(url_for('_root'))  # TODO: remember the origin and redirect there
        else:
            return abort(401)
    else:
        return render_template("login.html")


@app.route("/logout")
@login_required
def _logout():   #TODO: check for CSRF
    logout_user()
    return redirect(url_for('_root'))


@app.errorhandler(401)
def _page_not_found(e):
    return '<p>Login failed. <a href="' + url_for('_root') + '">Go back</a></p>'


@login_manager.user_loader
def _load_user(userid):
    return User(userid)


if __name__ == "__main__":  # pragma: no cover
    log.info("ui started")
    node_id, client_port = args_init()
    config = Config(node_id=node_id)
    # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    # app.run(host='0.0.0.0', port=client_port)
    # for pycharm debugging

    app.run(host='0.0.0.0', port=client_port, debug=True, use_debugger=False, use_reloader=False)
    __end()
