#!/usr/bin/env python

import argparse
import logging
import sys
import os
import zlib
import diff_match_patch
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


# to avoid race conditions existence of the item and creation should be done in a transaction
@firestore.transactional
def create_in_transaction(transaction, item_ref, item_rev, item_create_date):
    try:
        try:
            item_exist = item_ref.get(transaction=transaction)

            log.error("Tried to create the item but it's already been created")
            return False  # it shouldn't be there
        except google.api.core.exceptions.NotFound:
            transaction.set(item_ref, {
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
    log.debug("creation enqueued correctly")
    return True


def server_create_item(config):
    log.debug("server_create_item transaction")

    node_id = config.node_id
    item_node_id = config.item_node_id
    item_id = config.item_id
    item_rev = config.item_rev
    item_create_date = config.item_create_date

    db = firestore.Client()
    server_node_ref = db.collection('nodes').document(node_id)
    other_node_ref = server_node_ref.collection('other_nodes').document(item_node_id)
    item_ref = other_node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    log.debug("trying to create /nodes/{}/other_nodes/{}/items/{}".format(node_id,item_node_id,item_id,))

    result = create_in_transaction(transaction, item_ref, item_rev, item_create_date)
    if result:
        log.debug('transaction ended OK')
        return True
    else:
        log.error('ERROR saving new item')
        return False


# to avoid race conditions existence of the item and creation should be done in a transaction
@firestore.transactional
def enqueue_update_in_transaction(transaction, item_ref, item_rev, item_create_date, item_patches, old_shadow_adler32, shadow_adler32):
    try:
        try:
            log.debug("checking if the item exists")
            item_exist = item_ref.get(transaction=transaction)
            # exists so we can continue
        except google.api.core.exceptions.NotFound:
            log.error("item_exist doesn't... exist")
            return False  # it doesn't exists
        try:
            patches_ref = item_ref.collection('patches').document(str(item_rev))
            patches_exist = patches_ref.get(transaction=transaction)
            log.error("patches_exist... exists")
            return False  # it shouldn't be there
        except google.api.core.exceptions.NotFound:
            log.debug("patches_exist doesn't exist, creating")

            #patches = item_ref.collection('patches').get()
            item = item_ref.get().to_dict()

            log.debug("item: {}".format(item))
            try:
                shadow = item['shadow']
            except KeyError:
                shadow = None
            try:
                client_rev = item['client_rev']
            except KeyError:
                log.error("KeyError with client_rev")
                return False

            if not shadow:
                shadow = ''

            test_shadow = zlib.adler32(shadow.encode())
            if old_shadow_adler32 != test_shadow:
                log.error("shadows adler32s don't match {} {}".format(old_shadow_adler32, test_shadow,))
                return False

            if (client_rev + 1) != item_rev:
                log.error("client_rev: {}, item_rev: {}".format(client_rev, item_rev,))
                return False

            log.debug(item_patches)
            diff_obj = diff_match_patch.diff_match_patch()
            # these are FRAGILE patches and must match perfectly
            diff_match_patch.Match_Threshold = 0
            diff_match_patch.Match_Distance = 0
            patches = diff_obj.patch_fromText(item_patches)
            new_item_shadow, success = diff_obj.patch_apply(patches, shadow)

            if not success:
                log.debug("patching failed")
                return False
            else:
                log.debug("patching results: {}".format(new_item_shadow))

            test_shadow = zlib.adler32(new_item_shadow.encode())
            if shadow_adler32 != test_shadow:
                log.error("new shadows adler32s don't match {} {}".format(shadow_adler32, test_shadow,))
                return False

            # TODO: think in maybe save the CRC to avoid recalculating but it makes more complex updating the DB by hand...

            log.debug("updating patches_ref to: {}".format(item_rev))
            transaction.set(patches_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'other_node_create_date': item_create_date,
                'client_rev': item_rev,
                'patches': item_patches,
            })

            log.debug("updating client_rev to: {}".format(item_rev))
            transaction.set(item_ref, {
                'last_update_date': firestore.SERVER_TIMESTAMP,
                'client_rev': item_rev,
                'shadow': new_item_shadow,
            })

    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        return False
    log.debug("update enqueued correctly")
    return True


def server_update_item(config):
    node_id = config.node_id
    # item_user_id = config.item_user_id
    item_node_id = config.item_node_id
    item_id = config.item_id
    # item_action = config.item_action
    item_rev = config.item_rev
    item_create_date = config.item_create_date
    item_patches = config.item_patches
    old_shadow_adler32 = config.old_shadow_adler32
    shadow_adler32 = config.shadow_adler32

    db = firestore.Client()
    server_node_ref = db.collection('nodes').document(node_id)
    other_node_ref = server_node_ref.collection('other_nodes').document(item_node_id)
    item_ref = other_node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    log.debug("trying to update /nodes/{}/other_nodes/{}/items/{}".format(node_id, item_node_id, item_id,))

    result = enqueue_update_in_transaction(transaction, item_ref, item_rev, item_create_date, item_patches, old_shadow_adler32, shadow_adler32)
    if result:
        log.debug('transaction ended OK')
        return True
    else:
        log.error('ERROR updating item')
        return False


@app.errorhandler(405)
def errorhandler405(e):
    return Response('405', 405, {'Allow':'POST'})


def parse_req(req_json):
    log.debug("parse_req: {}".format(req_json))
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

    try:
        old_shadow_adler32 = req_json['old_shadow_adler32']
        shadow_adler32 = req_json['shadow_adler32']
    except KeyError:
        log.debug("missing old_shadow_adler32 or shadow_adler32")
        log.error("HTTP 400 Bad Request")
        abort(400)
    return item_action, item_rev, item_create_date, item_patches, old_shadow_adler32, shadow_adler32


def execute_item_action(config):
    # node_id = config.node_id
    # item_user_id = config.item_user_id
    # item_node_id = config.item_node_id
    # item_id = config.item_id
    item_action = config.item_action
    # item_rev = config.item_rev
    # item_create_date = config.item_create_date
    item_patches = config.item_patches

    if (item_action == "create_item" and item_patches) or (item_action == "edit_item" and not item_patches):
        log.error("unexpected patches or action, malformed request")
        log.error("HTTP 400 Bad Request")
        abort(400)

    try:
        if item_action == "create_item":
            log.debug("create_item contents seem OK, creating new item and shadow")
            if server_create_item(config):
                log.debug("HTTP 201: Created")
                return '', 201  # HTTP 201: Created
            else:
                log.debug("HTTP 204 No Content")
                return '', 204  # HTTP 204 No Content - Item already exists...
        elif item_action == "edit_item":
            log.debug("edit_item seems OK, updating item")
            if server_update_item(config):
                log.debug("HTTP 201: Created")
                return '', 201  # HTTP 201: Created
            else:
                log.error("HTTP 404 Not Found")
                abort(404)  # 404 Not Found
        else:
            log.error("don't know what is that action")
            log.error("HTTP 400 Bad Request")
            abort(400)  # 400 Bad Request
    except:
        log.error("Unknown error")
        abort(500)  # 500 Internal Server Error


@app.route('/users/<string:item_user_id>/nodes/<string:item_node_id>/items/<string:item_id>', methods=['POST'])
def _get_sync(item_user_id, item_node_id, item_id):
    if request.method == 'POST':
        config = AbrimConfig(node_id="node_2")
        config.item_user_id = item_user_id
        config.item_node_id = item_node_id
        config.item_id = item_id
        config.item_action, config.item_rev, config.item_create_date, config.item_patches, config.old_shadow_adler32, config.shadow_adler32 = parse_req(request.get_json())

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
    #
    config = AbrimConfig(node_id="node_2")
    #
    # config.item_user_id = "user_1"
    # config.node_id = "test_node2"
    # config.item_id = "item_1"
    # config.item_create_date = "2018 - 01 - 29T21: 35:15.785000 + 00: 00"
    # config.item_action = "create_item"
    # config.item_node_id = "node_1"
    # config.item_rev = 0
    #
    # server_create_item(config)
    #
    #
    # config.item_user_id = "user_1"
    # config.node_id = "test_node2"
    # config.item_id = "item_1"
    # config.item_create_date = "2018-02-03T21:46:32.785000+00:00"
    # config.item_action = "edit_item"
    # config.item_node_id = "node_1"
    # config.item_rev = 1
    # config.item_patches = '@@ -0,0 +1,10 @@\n+a new text\n'
    #
    # server_update_item(config)

    # config.item_patches = "@@ -1,10 +1,12 @@\n a new\n+er\n  text\n"
    # config.node_id = "node_2"
    # config.item_create_date = "2018-03-11T17:08:25.774000+00:00"
    # config.item_user_id = "user_1"
    # config.item_rev = 2
    # config.item_id = "item_1"
    # config.item_node_id = "node_1"
    # config.item_action = "edit_item"
    #
    # server_update_item(config)
    #
    # sys.exit(0)











    # db = firestore.Client()
    # server_node_ref = db.collection('nodes').document('node_2')
    # other_node_ref = server_node_ref.collection('other_nodes').document('node_1')
    # item_ref = other_node_ref.collection('items').document('item_1')
    #
    # item_ref.set({
    #     'last_update_date': firestore.SERVER_TIMESTAMP,
    #     'client_rev': 2,
    #     'shadow': "a newer text",
    # })
    #
    # patches_ref = item_ref.collection('patches').document("1")
    # patches_ref.set({
    #     'create_date': firestore.SERVER_TIMESTAMP,
    #     'other_node_create_date': "2018-03-11T17:36:42.672000+00:00",
    #     'client_rev': 1,
    #     'patches': "@@ -0,0 +1,10 @@ +a new text",
    # })
    #
    # patches_ref2 = item_ref.collection('patches').document("2")
    # patches_ref2.set({
    #     'create_date': firestore.SERVER_TIMESTAMP,
    #     'other_node_create_date': "2018-03-11T17:36:47.798000+00:00",
    #     'client_rev': 2,
    #     'patches': "@@ -1,10 +1,12 @@ a new +er text ",
    # })
    #
    #
    #
    #
    # sys.exit(0)



    # previous to test update 1
    # db = firestore.Client()
    # server_node_ref = db.collection('nodes').document('node_2')
    # other_node_ref = server_node_ref.collection('other_nodes').document('node_1')
    # item_ref = other_node_ref.collection('items').document('item_1')
    #
    # item_ref.set({
    #     'last_update_date': firestore.SERVER_TIMESTAMP,
    #     'client_rev': 0,
    # })
    #
    # patches_ref = item_ref.collection('patches').document("1")
    # patches_ref.delete()

    client_port = _init()
    # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    # app.run(host='0.0.0.0', port=client_port)
    # for pycharm debugging
    app.run(host='0.0.0.0', port=client_port, debug=True, use_debugger=False, use_reloader=False)
    __end()
