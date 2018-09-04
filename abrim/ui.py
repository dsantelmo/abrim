#!/usr/bin/env python

import traceback
import time
import requests
from flask import Flask, request, abort, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from abrim.config import Config
from abrim.util import get_log, fragile_patch_text, resp, check_fields_in_dict, check_crc, get_crc, create_diff_edits, \
                       create_hash, args_init, response_parse

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


def _test_password(username, password):
    return True


def __end():
    # db.close_db()
    pass


def _check_list_items(raw_response):
    if raw_response:
        api_unique_code, response_http, response_dict = response_parse(raw_response)
        if response_http == 200 and api_unique_code == "queue_in/get_items/200/ok":

            log.debug(response_dict)
            return response_dict
        else:
            return None
    else:
        return None


def _list_items():
    """curl -X GET http://127.0.0.1:5001/users/user_1/nodes/node_1/items -H "Authorization: Basic YWRtaW46c2VjcmV0" -H "content-type: application/json"
"""
    url = "http://127.0.0.1:5001/users/user_1/nodes/node_1/items"

    payload = "{\n \"rowid\": 1,\n \"item\": \"item_1\",\n \"other_node\": \"node_2\",\n \"n_rev\": 0,\n \"m_rev\": 0,\n \"shadow_adler32\": \"1\",\n \"old_shadow_adler32\": \"1\",\n \"edits\": \"\"\n}"
    headers = {
        'content-type': "application/json",
        'authorization': "Basic YWRtaW46c2VjcmV0",
    }
    log.debug("requesting {}".format(url))
    try:
        raw_response = requests.get(url, data=payload, headers=headers, timeout=1)
    except requests.exceptions.ConnectTimeout:
        return None, False
    else:
        response_dict = _check_list_items(raw_response)
        if response_dict:
            try:
                content = response_dict['content']
                log.debug(content)
                return content, True
            except KeyError:
                return None, True
        else:
            return None, True


@app.before_request
def before_request():
    # db.prepare_db_path(app.config['DB_PATH'])
    pass


@app.teardown_request
def teardown_request(exception):
    __end()


@app.route('/', methods=['GET'])
@login_required
def _root():
    # if not current_user.is_authenticated:
    #     return redirect(url_for('_login'))
    content, conn_ok = _list_items()
    return render_template('list.html', conn_ok=conn_ok, content=content)


@app.route('/nodes/<string:node_id>/items/<string:item_id>', methods=['GET'])
@login_required
def _get_item(node_id, item_id):
    return "ok"


@app.route('/login', methods=['GET', 'POST'])
def _login():
    if  current_user.is_authenticated:
        return redirect(url_for('_root'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        #node = request.form['node']
        #port = request.form['port']

        #if _test_password(username, password, node, port):
        if _test_password(username, password):
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
    log.info("{} started".format(__file__))
    node_id, client_port = args_init()

    if not node_id or not client_port:
        __end()
    else:
        config = Config(node_id=node_id)
        # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
        # app.run(host='0.0.0.0', port=client_port)
        # for pycharm debugging

        app.run(host='0.0.0.0', port=client_port, debug=False, use_debugger=False, use_reloader=False)
        __end()
