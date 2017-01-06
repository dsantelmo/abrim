#!/usr/bin/env python

from contextlib import closing
import os
import sys
import argparse
import logging
from flask import Flask, g, request, redirect, url_for, abort, render_template, flash, jsonify
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.db import db
from abrim.sync import client_sync


# http://stackoverflow.com/questions/1623039/python-debugging-tips
LOGGING_LEVELS = {'critical': logging.CRITICAL,
                  'error': logging.ERROR,
                  'warning': logging.WARNING,
                  'info': logging.INFO,
                  'debug': logging.DEBUG}
# FIXME http://docs.python-guide.org/en/latest/writing/logging/
# It is strongly advised that you do not add any handlers other
# than NullHandler to your library's loggers.
logging.basicConfig(level=logging.DEBUG,
              format='%(asctime)s __ %(module)-12s __ %(levelname)-8s: %(message)s',
              datefmt='%Y-%m-%d %H:%M:%S')  # ,
              # disable_existing_loggers=False)
logging.StreamHandler(sys.stdout)
log = logging.getLogger(__name__)


app = Flask(__name__)
# Default config:
app.config['APP_NAME'] = "Sync"
app.config['APP_AUTHOR'] = "Abrim"
app.config['DIFF_TIMEOUT'] = 0.1
app.config['MAX_RECURSIVE_COUNT'] = 3
app.config['DB_FILENAME_FORMAT'] = 'abrimsync-{}.sqlite'
app.config['DB_SCHEMA_PATH'] = os.path.join('db', 'schema.sql')

# Config from files and env vars:
# config_files.load_app_config(app)  # breaks in travis
app.config.from_envvar('ABRIMSYNC_SETTINGS', silent=True)


@app.route('/users/<string:user_id>/nodes/<string:node_id>/items', methods=[ 'GET'])
def _send_sync(user_id, node_id):
    if request.method == 'GET':
        return items_receive_get(user_id, node_id)
    else:
        log.debug("HTTP 404 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(404)


@app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>', methods=['GET', 'POST', 'PUT'])
def _get_sync(user_id, node_id, item_id):
    if request.method == 'POST':
        return items_receive_post_by_id(user_id, node_id, item_id, request)  # FIXME check response correctness here?
    elif request.method == 'PUT':
        return items_receive_put_by_id(user_id, node_id, item_id, request)  # FIXME check response correctness here?
    elif request.method == 'GET':
        return items_receive_get_by_id(user_id, node_id, item_id)
    else:
        log.debug("HTTP 404 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(404)

### @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>/shadow', methods=['POST'])
### def _send_shadow(user_id, node_id, item_id):
###     if request.method != 'POST':
###         log.debug("HTTP 404 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###         abort(404)
###     else:
###         return receive_shadow(user_id, node_id, item_id, request)


def items_receive_get(user_id, node_id, item_id=None):
    if not item_id:
        log.debug("items_receive_get: GET the list")
        #
        items = db.get_user_node_items(user_id, node_id)
        res = {
            'status': 'OK',
            'items': items,
            }
        log.debug("items_receive_get - response: " + str(res))
        return jsonify(**res)
    else:
        log.debug("items_receive_get: GET one item by ID - " + item_id)
        item = get_user_node_item_by_id(user_id, node_id, item_id)
        if item is None:
            log.debug("HTTP 404 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
            abort(404)
        res = {
            'status': 'OK',
            'item': item,
            }
        log.debug("items_receive_get - response: " + str(res))
        return jsonify(**res)


def items_receive_get_by_id(user_id, node_id, item_id):
    return items_receive_get(user_id, node_id, item_id)


# FIXME create a generic checker for json attributes and error responses
def items_receive_post_by_id(user_id, node_id, item_id, request):
    """Receives a new item, saves it locally and then it tries to sync it (that can fail)"""
    req = request.json
    if req and 'content' in req:
        #
        # move to external lib
        #
        if db.create_item(item_id, node_id, user_id, req['content']):
            #
            #
            # item ready, now we try to sync it and generate a shadow
            client_sync(user_id, node_id, item_id, req['content'], app.config['DIFF_TIMEOUT'])
            #
            #
            log.debug("items_receive_post_by_id - response: 201")
            return '', 201
        else:
            log.warning("HTTP 409 - Conflict: An item with that ID already exists")
            abort(409)
    else:
        if not req:
            log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
            abort(415)
        else:
            log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
            abort(422)


def items_receive_put_by_id(user_id, node_id, item_id, request):
    """Receives a new item or an update to an item, saves it locally and then it tries to sync it (that can fail)"""
    req = request.json
    if req and 'content' in req:
        #
        # move to external lib
        #
        content = db.get_content(user_id, node_id, item_id)
        if content is None:
            response_code = 201  # HTTP 201: Created
        else:
            response_code = 204  # HTTP No Content - Item already exists... FIXME: race condition between get and set? maybe create an atomic operation
        if db.set_content(user_id, node_id, item_id, req['content']):
            #
            # item ready, now we try to sync it and generate a shadow
            #
            #
            log.debug("items_receive_put_by_id - response: " + str(response_code))
            return '', response_code
        else:  # pragma: no cover
            log.error("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
            abort(500)
    else:
        if not req:
            log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
            abort(415)
        else:
            log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
            abort(422)


def get_user_node_item_by_id(user_id, node_id, item_id):
    # FIXME change to use item_id
    log.debug("get_user_node_item_by_id -> " + user_id + " - " + node_id + " - " + item_id)
    content = db.get_content(user_id, node_id, item_id)
    shadow = db.get_shadow(user_id, node_id, item_id)
    if not content:
        log.debug("get_user_node_item_by_id - not found: " + item_id)
        return None
    else:
        return {"item_id": item_id, "content": content, "shadow": shadow}


def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None, None
    return args.port, args.logginglevel, args.initdb


def _init():
    #import pdb; pdb.set_trace()
    log.info("Hajime!")
    args_port, args_logginglevel, args_initdb = _parse_args_helper()
    if args_port and int(args_port) > 0:
        client_port = int(args_port)
        app.config['API_URL'] = "http://127.0.0.1:" + str( int(args_port)+1 )
        app.config['NODE_PORT'] = client_port
        # FIXME client side config
        app.config['USER_ID'] = "the_user"
        app.config['NODE_ID'] = "node" + args_port
    else:
        print("use -p to specify a port")
        abort(500)
    if args_logginglevel:
        logging_level = LOGGING_LEVELS.get(args_logginglevel, logging.NOTSET)
        log.setLevel(logging_level)
    log.debug("DEBUG logging enabled")
    app.config['DB_PATH'] = db.get_db_path(app.config['DB_FILENAME_FORMAT'], app.config['NODE_ID'])
    # before_request()
    if args_initdb:
        db.init_db(app)
    return client_port


def __end():
    db.close_db()


@app.before_request
def before_request():
    db.prepare_db_path(app.config['DB_PATH'])


@app.teardown_request
def teardown_request(exception):
    __end()


if __name__ == "__main__":  # pragma: no cover
    client_port = _init()
    #app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    app.run(host='0.0.0.0', port=client_port)
    __end()