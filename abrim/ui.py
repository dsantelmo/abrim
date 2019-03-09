#!/usr/bin/env python

from flask import Flask, session, request, abort, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from abrim.config import Config
from abrim.util import get_log, args_init, response_parse, get_request, post_request, put_request, ROUTE_FOR

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


def _test_password(username, password, node):
    url = f"{node}/auth"
    raw_response = get_request(url, username, password)

    if not raw_response:
        log.debug("connection error")
        return False
    else:
        api_unique_code, response_http, _ = response_parse(raw_response)
        if response_http != 200 or api_unique_code != "queue_in/auth/200/ok":
            log.warning(f"bad response_http ({response_http}) or api_unique_code ({api_unique_code})")
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
    

def _check_list_nodes(raw_response):
    if raw_response:
        api_unique_code, response_http, response_dict = response_parse(raw_response)
        if response_http == 200 and api_unique_code == "queue_in/get_nodes/200/ok":

            log.debug(response_dict)
            return response_dict
        else:
            return None
    else:
        return None


def _list_items(username, password):
    url = f"{session['user_node']}{ROUTE_FOR['items']}"  #fixme
    try:
        raw_response = get_request(url, username, password)
    except ConnectionError:
        log.debug("ConnectionError")
        return None, False, True

    if not raw_response and raw_response.status_code != 404:
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
                log.error(f"KeyError in {response_dict}")
                return None, True, True
        else:
            if raw_response.status_code == 401:
                log.warning("not auth")
                return None, True, False
            if raw_response.status_code == 404:
                return None, True, True
            else:
                log.warning(f"no response_dict in {raw_response}")
                return None, False, True


def _list_nodes(username, password):
    url = f"{session['user_node']}{ROUTE_FOR['nodes']}"  # fixme
    raw_response = get_request(url, username, password)

    if not raw_response and raw_response.status_code != 404:
        log.debug("connection error")
        return None, False, True
    else:
        response_dict = _check_list_nodes(raw_response)
        if response_dict:
            try:
                content = response_dict['content']
                log.debug(content)
                return content, True, True
            except KeyError:
                log.error(f"KeyError in {response_dict}")
                return None, True, True
        else:
            if raw_response.status_code == 401:
                log.warning("not auth")
                return None, True, False
            if raw_response.status_code == 404:
                return None, True, True
            else:
                log.warning(f"no response_dict {raw_response}")
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


def _req_get_item(username, password, item_id):
    # returns: content, conn_ok, auth_ok
    url = f"{session['user_node']}{ROUTE_FOR['items']}/{item_id}"
    raw_response = get_request(url, username, password)

    if not raw_response:
        if raw_response.status_code == 404:
            log.debug("404 not found")
        else:
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
                log.error(f"KeyError in {response_dict}")
                return None, True, True
        else:
            if raw_response.status_code == 401:
                log.warning("not auth")
                return None, True, False
            else:
                log.warning(f"no response_dict in {raw_response}")
                return None, False, True


@app.before_request
def before_request():
    if request.full_path and request.method:
        log.debug(f"{request.method} REQUEST: {request.full_path}")
    else:
        log.error("request doesn't have a full_path and/or method")
        return redirect(url_for('_root'))
    try:  # TODO is doing this secure?
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
                                                session['current_user_password'])
        return render_template('list.html', conn_ok=conn_ok, auth_ok=auth_ok, content=content)
    except KeyError:
        log.debug("AttributeError, logging out")
        logout_user()
        return redirect(url_for('_root'))


@app.route(ROUTE_FOR['nodes'], methods=['GET', 'POST'])
@login_required
def _nodes():
    if request.method == 'GET':
        try:
            content, conn_ok, auth_ok = _list_nodes(session['current_user_name'],
                                                    session['current_user_password'])
            return render_template('nodes.html', conn_ok=conn_ok, auth_ok=auth_ok, content=content)
        except KeyError:
            log.debug("AttributeError, logging out")
            logout_user()
            return redirect(url_for('_root'))
    else:
        try:
            new_node_base_url = request.form['new_node_base_url']
            log.debug(new_node_base_url)
        except IndexError:
            log.debug("_new IndexError")
            return redirect(url_for('_nodes'))
        except KeyError:
            log.debug("_new KeyError")
            return redirect(url_for('_nodes'))

        url = f"{session['user_node']}{ROUTE_FOR['nodes']}" #fixme
        post_request(url, {"new_node_base_url": new_node_base_url}, session['current_user_name'], session['current_user_password'])

        return redirect(url_for('_nodes'))



@app.route(f"{ROUTE_FOR['items']}/<string:item_id>", methods=['GET'])
@login_required
def _get_item(item_id):
    log.debug("_get_item")
    try:
        content, conn_ok, auth_ok = _req_get_item(session['current_user_name'],
                                                session['current_user_password'],
                                                item_id)
        return render_template('item.html', conn_ok=conn_ok, auth_ok=auth_ok, item_id=item_id, content=content, edit=False)
    except AttributeError:
        log.debug("AttributeError, logging out")
        logout_user()
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


@app.route('/new', methods=['GET'])
@login_required
def _get_new():
    log.debug("_get_new")
    return render_template("new.html", auth_ok=True)


@app.route('/new', methods=['POST'])
@login_required
def _post_new():
    log.debug("_post_new")
    try:
        item_id = request.form['item_id']
        client_text = request.form['client_text']
        log.debug(item_id)
        log.debug(client_text)
    except IndexError:
        log.debug("_new IndexError")
        return render_template("new.html", auth_ok=True, item_id=item_id, client_text=client_text)
    except KeyError:
        log.debug("_new KeyError")
        return render_template("new.html", auth_ok=True, item_id=item_id, client_text=client_text)

    url = f"{session['user_node']}{ROUTE_FOR['items']}/{item_id}"
    put_request(url, {"text": client_text}, session['current_user_name'], session['current_user_password'])
    return redirect(url_for('_get_item', node_id=node_id, item_id=item_id, _method='GET'))


@app.route(f"{ROUTE_FOR['items']}/<string:item_id>", methods=['POST'])
@login_required
def _post_item(item_id):
    log.debug("_post_item")
    if 'update' in request.args and 'client_text' in request.form:
        log.debug("_post_item-update")
        url = f"{session['user_node']}{ROUTE_FOR['items']}/{item_id}"
        post_request(url, {"text": request.form['client_text']}, session['current_user_name'], session['current_user_password'])

        return redirect(url_for('_get_item', item_id=item_id, _method='GET'))
    elif 'edit' in request.args:
        log.debug("_post_item-edit")
        try:
            content, conn_ok, auth_ok = _req_get_item(session['current_user_name'],
                                                    session['current_user_password'],
                                                    item_id)
            return render_template('item.html', conn_ok=conn_ok, auth_ok=auth_ok, item_id=item_id, content=content, edit=True)
        except AttributeError:
            log.debug("AttributeError, logging out")
            logout_user()
            return redirect(url_for('_root'))
    else:
        log.debug("_post_item-error")
        log.error("error in _post_item")
        return redirect(url_for('_root'))


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
    log.info(f"{__file__} started")
    node_id, client_port = args_init()

    if not node_id or not client_port:
        __end()
    else:
        config = Config(node_id, client_port)
        # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
        # app.run(host='0.0.0.0', port=client_port)
        # for pycharm debugging

        app.run(host='0.0.0.0', port=client_port, debug=False, use_debugger=False, use_reloader=False)
        __end()
