#!/usr/bin/env python

import argparse
import logging
import sys
import os
from google.cloud import firestore
import grpc
import google

from flask import Flask, request, abort, jsonify, Response

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from node import AbrimConfig

full_debug = False
if full_debug:
    # enable debug for HTTP requests
    import http.client as http_client
    http_client.HTTPConnection.debuglevel = 1
else:
    # disable more with
    # for key in logging.Logger.manager.loggerDict:
    #    print(key)
    logging.getLogger('werkzeug').setLevel(logging.CRITICAL)


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


def server_create_item(config):
    log.debug("server_create_item transaction")

    node_id = config.node_id
    item_user_id = config.item_user_id
    item_node_id = config.item_node_id
    item_id = config.item_id
    item_rev = config.item_rev
    item_create_date = config.item_create_date

    db = firestore.Client()
    server_node_ref = db.collection('nodes').document(node_id)
    other_node_ref = server_node_ref.collection('other_nodes').document(item_node_id)
    item_ref = other_node_ref.collection('items').document(item_id)

    transaction1 = db.transaction()

    @firestore.transactional
    def create_in_transaction(transaction1, node_id, item_user_id, item_node_id, item_id, item_rev, item_create_date):
        try:
            server_node_ref = db.collection('nodes').document(node_id)
            other_node_ref = server_node_ref.collection('other_nodes').document(item_node_id)
            item_ref = other_node_ref.collection('items').document(item_id)

            transaction1.set(item_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'other_node_create_date': item_create_date,
                'client_rev': item_rev,
            })
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            log.error("Connection error to Firestore")
            return False
        log.debug("edit enqueued")
        return True

    result = create_in_transaction(transaction1, node_id, item_user_id, item_node_id, item_id, item_rev, item_create_date)
    if result:
        log.debug('transaction ended OK')
    else:
        log.error('ERROR saving new item')
        raise Exception


def server_update_item(config):
    # node_id = config.node_id
    # item_user_id = config.item_user_id
    # item_node_id = config.item_node_id
    # item_id = config.item_id
    # item_action = config.item_action
    # item_rev = config.item_rev
    # item_create_date = config.item_create_date
    # item_patches = config.item_patches


    log.error('ERROR saving new item')
    raise Exception


# to test:
#
# import requests
#
# url = "http://127.0.0.1:5001/users/user_1/nodes/node_1/items/item_1"
#
# payload = "{\n\t\"action\": \"create_item\",\n\t\"create_date\": \"2018-01-29T21:35:15.785000+00:00\",\n\t\"client_rev\": 0\n}"
#
# headers = {
#     'Content-Type': "application/json",
#     'Cache-Control': "no-cache",
#     'Postman-Token': "173c0991-7697-8506-bbdb-f433d4909c20"
#     }
#
#
# response = requests.request("POST", url, data=payload, headers=headers)
# print(response.status_code)
#
# or:
# import http.client
#
# conn = http.client.HTTPConnection("127.0.0.1:5001")
#
# payload = "{\n\t\"action\": \"create_item\",\n\t\"create_date\": \"2018-01-29T21:35:15.785000+00:00\",\n\t\"client_rev\": 0\n}"
#
# headers = {
#     'Content-Type': "application/json",
#     'Cache-Control': "no-cache",
#     'Postman-Token': "0cf06ca7-5611-8aed-3739-14bde335ef00"
#     }
#
#
# conn.request("POST", "users/user_1/nodes/node_1/items/item_1", payload, headers)
#
# res = conn.getresponse()
# #data = res.read()
# #print(data.decode("utf-8"))
# print(res.code)

@app.errorhandler(405)
def errorhandler405(e):
    return Response('405', 405, {'Allow':'POST'})


def parse_req(req_json):
    try:
        item_action = req_json['action']
        item_rev = req_json['client_rev']
        item_create_date = req_json['create_date']
    except KeyError:
        log.error("missing action or client_rev or create_date")
        log.error("HTTP 400 Bad Request")
        abort(400)

    try:
        item_patches = req_json['text_patches']
    except KeyError:
        log.debug("no patches")
        item_patches = None
    return item_action, item_rev, item_create_date, item_patches


def execute_item_action(config):
    # node_id = config.node_id
    # item_user_id = config.item_user_id
    # item_node_id = config.item_node_id
    # item_id = config.item_id
    # item_action = config.item_action
    # item_rev = config.item_rev
    # item_create_date = config.item_create_date
    # item_patches = config.item_patches

    item_action = config.item_action
    item_patches = config.item_patches

    if item_action == "create_item" and item_patches:
        log.error("unexpected patches in action create_item, malformed request")
        log.error("HTTP 400 Bad Request")
        abort(400)

    if item_action == "edit_item" and not item_patches:
        log.error("missing patches in action edit_item, malformed request")
        log.error("HTTP 400 Bad Request")
        abort(400)

    if item_action == "create_item":
        log.debug("create_item seems OK, creating new item and shadow")
        try:
            server_create_item(config)
            return '', 201  # HTTP 201: Created
        except:
            log.error("Unknown error")
            abort(500)  # 500 Internal Server Error
    elif item_action == "edit_item":
        log.debug("edit_item seems OK, updating item")
        try:
            server_update_item(config)
            return '', 201  # HTTP 201: Created
        except:
            log.error("Unknown error")
            abort(500)  # 500 Internal Server Error
    else:
        log.error("don't know what is that action")
        log.error("HTTP 400 Bad Request")
        abort(400)  # 400 Bad Request


@app.route('/users/<string:item_user_id>/nodes/<string:item_node_id>/items/<string:item_id>', methods=['POST'])
def _get_sync(item_user_id, item_node_id, item_id):
    if request.method == 'POST':
        config = AbrimConfig(node_id="node_2")
        config.item_user_id = item_user_id
        config.item_node_id = item_node_id
        config.item_id = item_id
        config.item_action, config.item_rev, config.item_create_date, config.item_patches = parse_req(request.get_json())

        x = 0
        for item in vars(config).items():
            x += 1
            log.debug("{}. {}: {} ({})".format(x, item[0],item[1],type(item[1])))

        return execute_item_action(config)
    else:
        log.debug("HTTP 405 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(405)  # 405 Method Not Allowed



def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    #parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None
    return args.port, args.logginglevel #, args.initdb



def _init():
    #import pdb; pdb.set_trace()
    log.info("Hajime!")
    args_port, args_logginglevel = _parse_args_helper()
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
    # before_request()
    return client_port


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


if __name__ == "__main__":  # pragma: no cover
    client_port = _init()
    # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    # app.run(host='0.0.0.0', port=client_port)
    # for pycharm debugging
    app.run(host='0.0.0.0', port=client_port, debug=True, use_debugger=False, use_reloader=False)
    __end()
