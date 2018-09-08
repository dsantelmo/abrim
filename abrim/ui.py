#!/usr/bin/env python

import traceback
import time
import requests
from base64 import b64encode
from flask import Flask, session, request, abort, render_template, redirect, url_for
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
login_manager.login_message_category = "info"


class User(UserMixin):
    def __init__(self, name, active=True):
        self.name = name
        self.id = name
        self.active = active

    def __repr__(self):
        return "%s/%s/%s" % (self.id, self.name, self.active)


def _get_request(username, password, node, url_path, payload=None):
    url = node + url_path
    auth_basic = b64encode(username.encode('utf-8') + b":" + password.encode('utf-8')).decode("ascii")
    headers = {
        'content-type': "application/json",
        'authorization': "Basic {}".format(auth_basic),
    }
    log.debug("requesting {}".format(url))
    try:
        if payload:
            raw_response = requests.get(url, data=payload, headers=headers, timeout=1)
        else:
            raw_response = requests.get(url, headers=headers, timeout=1)
    except requests.exceptions.ConnectTimeout:
        log.warning("ConnectTimeout")
        return None
    except requests.exceptions.MissingSchema:
        log.warning("MissingSchema")
        return None
    else:
        return raw_response

def _test_password(username, password, node):
    url_path = "/auth"
    raw_response = _get_request(username, password, node, url_path)

    if not raw_response:
        log.debug("connection error")
        return False
    else:
        api_unique_code, response_http, _ =  response_parse(raw_response)
        if response_http != 200 or api_unique_code != "queue_in/auth/200/ok":
            log.warning("bad response_http ({}) or api_unique_code ({})".format(response_http, api_unique_code))
            return False
        else:
            log.debug("auth OK")
            return True


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


def _list_items(username, password, node):
    url_path = "/users/user_1/nodes/node_1/items"  #FIXME change it so it doesn't ask for user and node
    raw_response = _get_request(username, password, node, url_path)

    if not raw_response:
        log.debug("connection error")
        return None, False, True
    else:
        response_dict = _check_list_items(raw_response)
        if response_dict:
            try:
                content = response_dict['content']
                log.debug(content)
                return content, True, True
            except KeyError:
                log.error("KeyError {}".format(response_dict))
                return None, True, True
        else:
            if raw_response.status_code == 401:
                log.warning("not auth")
                return None, True, False
            else:
                log.warning("no response_dict {}".format(raw_response))
                return None, False, True


def _check_get_items(raw_response):
    if raw_response:
        api_unique_code, response_http, response_dict = response_parse(raw_response)
        if response_http == 200 and api_unique_code == "queue_in/get_text/200/ok":

            log.debug(response_dict)
            return response_dict
        else:
            return None
    else:
        return None


def _req_get_item(username, password, node, node_id_, item_id):
    url_path = "/users/{}/nodes/{}/items/{}".format(username, node_id_, item_id)
    raw_response = _get_request(username, password, node, url_path)

    if not raw_response:
        log.debug("connection error")
        return None, False, True
    else:
        response_dict = _check_get_items(raw_response)
        if response_dict:
            try:
                content = response_dict['content']
                log.debug(content)
                return content, True, True
            except KeyError:
                log.error("KeyError {}".format(response_dict))
                return None, True, True
        else:
            if raw_response.status_code == 401:
                log.warning("not auth")
                return None, True, False
            else:
                log.warning("no response_dict {}".format(raw_response))
                return None, False, True


@app.before_request
def before_request():  # TODO is doing this secure?
    try:
        session['current_user_name'] = current_user.name
        session['current_user_password'] = current_user.password
    except AttributeError:
        pass


@app.teardown_request
def teardown_request(exception):
    __end()


@app.route('/', methods=['GET'])
@login_required
def _root():
    try:
        content, conn_ok, auth_ok = _list_items(session['current_user_name'],
                                                session['current_user_password'],
                                                session['user_node'])
        return render_template('list.html', conn_ok=conn_ok, auth_ok=auth_ok, content=content)
    except AttributeError:
        log.debug("AttributeError, logging out")
        logout_user()
        return redirect(url_for('_root'))


@app.route('/nodes/<string:node_id>/items/<string:item_id>', methods=['GET','POST'])
@login_required
def _get_item(node_id, item_id):
    if request.method == 'GET':
        try:
            content, conn_ok, auth_ok = _req_get_item(session['current_user_name'],
                                                    session['current_user_password'],
                                                    session['user_node'], node_id, item_id)
            return render_template('item.html', conn_ok=conn_ok, auth_ok=auth_ok, item_id=item_id, content=content, edit=False)
        except AttributeError:
            log.debug("AttributeError, logging out")
            logout_user()
            return redirect(url_for('_root'))
    else:  # POST is used to print the textarea for edits and recover the sent edit (where ?update added to url)
        if 'update' in request.args and 'client_text' in request.form:
            new_item_text = request.form['client_text']
            print("UPDATE! {}".format(new_item_text))
        elif 'edit' in request.args:
            try:
                content, conn_ok, auth_ok = _req_get_item(session['current_user_name'],
                                                        session['current_user_password'],
                                                        session['user_node'], node_id, item_id)
                return render_template('item.html', conn_ok=conn_ok, auth_ok=auth_ok, item_id=item_id, content=content, edit=True)
            except AttributeError:
                log.debug("AttributeError, logging out")
                logout_user()
                return redirect(url_for('_root'))
        else:
            log.error("error in _get_item")
            return redirect(url_for('_root'))



@app.route('/login', methods=['GET', 'POST'])
def _login():
    if current_user.is_authenticated:
        return redirect(url_for('_root'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        node = request.form['node']

        if _test_password(username, password, node):
            try:
                user = User(username)
                login_user(user)
                session['current_user_name'] = username
                session['current_user_password'] = password # FIXME pretty sure this is NOT secure, use server-side secure cache or use nonces
                session['user_node'] = node
                session.modified = True
                return redirect(url_for('_root'))  # TODO: remember the origin and redirect there
            except IndexError:
                log.debug("_login IndexError")
                return abort(401)
        else:
            log.debug("_test_password failed")
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


def __end():
    # db.close_db()
    pass


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
