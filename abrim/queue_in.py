#!/usr/bin/env python

import argparse
import sys
import zlib
import traceback
from google.cloud import firestore
import grpc
import google
from flask import Flask, request, abort, Response
from abrim.config import Config
from abrim.util import get_log, patch_text, resp, check_fields_in_dict, check_request_method, check_crc


log = get_log(full_debug=False)

app = Flask(__name__)


# to avoid race conditions existence of the item and creation should be done in a transaction
@firestore.transactional
def enqueue_update_in_transaction(transaction, item_ref, config):
    try:
        item_rev = stored_server_rev + 1

        log.debug("updating patches_ref to: {}".format(item_rev))

        # /nodes/node_2/items/item_1/patches/node_1/revs/0
        patches_ref = item_ref.collection('patches').document(config.item_node_id).collection('revs').document(str(item_rev))
        transaction.set(patches_ref, {
            'create_date': firestore.SERVER_TIMESTAMP,
            'client_rev': item_rev,
            'patches': config.edits,
        })
        log.debug("updating client_rev to: {}".format(item_rev))

        shadow_ref = item_ref.collection('shadows').document(config.item_node_id).collection('revs').document(str(item_rev))
        transaction.set(shadow_ref, {
            'create_date': firestore.SERVER_TIMESTAMP,
            'shadow_client_rev': config.shadow_client_rev,
            'shadow_server_rev': item_rev,
            'shadow': new_item_shadow,
            'old_shadow': shadow  # FIXME check if this is really needed
        })

    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        return False
    log.debug("update enqueued correctly")
    return True


def _get_server_shadow(config, r_json):
    i_e = config.item_edit
    got_shadow, shadow = config.db.get_shadow(i_e['item_id'],
                                              i_e['item_node_id'],
                                              r_json['other_node_rev'],
                                              r_json['rev'])
    if got_shadow:
        log.debug("shadow: {}".format(shadow))
    return got_shadow, shadow


def _patch_server_shadow(config, shadow):
    if config.edits == "" and shadow == "":
        log.debug("no shadow or patches, nothing to patch...")
        new_item_shadow = ""
    else:
        new_item_shadow, success = patch_text(config.edits, shadow)
        if not success:
            log.debug("patching failed")
            return False
    log.error("IMPLEMENT ME")
    return False


def _check_request_ok(r_json):
    if not check_fields_in_dict(r_json, ('edits',)):
        log.debug("no edits")
    if not check_fields_in_dict(r_json, ('rev', 'other_node_rev', 'old_shadow_adler32', 'shadow_adler32',)):
        return False
    try:
        log.info("revs: {} - {}".format(r_json['rev'], r_json['other_node_rev']))
        log.info("has edits: {:.30}...".format(r_json['edits'].replace('\n', ' ')))
    except KeyError:
        log.info("edit request revs: {} - {}, no edits".format(r_json['shadow_client_rev'],
                                                               r_json['shadow_server_rev']))
    return True


def _check_shadow_request_ok(r_json):
    if not check_fields_in_dict(r_json, ('rev', 'other_node_rev', 'shadow',)):
        return False, _
    try:
        log.info("revs: {} - {}".format(r_json['rev'], r_json['other_node_rev']))
        log.info("has shadow: {:.30}...".format(r_json['shadow'].replace('\n', ' ')))
    except KeyError:
        log.error("no shadow in request")
        return False, _
    return True, r_json['shadow']


def _check_revs(config, r_json):
    saved_rev, saved_other_node_rev = config.db.get_oldest_revs(config.item_edit['item_id'], config.item_edit['item_node_id'])
    if r_json['rev'] != saved_other_node_rev:
        log.error("rev DOESN'T match: {} - {}".format(r_json['rev'], saved_other_node_rev))
        return False
    if r_json['other_node_rev'] != saved_rev:
        log.error("other_node_rev DOESN'T match: {} - {}".format(r_json['other_node_rev'], saved_other_node_rev))
        return False
    return saved_rev, saved_other_node_rev


def _check_permissions(dummy):  # TODO: implement me
    return True


def _check_item_exists(item_id):
    return config.db.get_item(item_id)


def _save_item(item_id, new_text):
    config.db.save_item(item_id, new_text)


def _save_shadow(other_node_id, item_id, shadow, rev, other_node_rev):
    config.db.save_new_shadow(other_node_id, item_id, shadow, rev, other_node_rev)


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['POST'])
def _get_sync(user_id, client_node_id, item_id):
    log.debug("got a request at /users/{}/nodes/{}/items/{}".format(user_id, client_node_id, item_id, ))

    config.item_edit = {"item_user_id": user_id, "item_node_id": client_node_id, "item_id": item_id}

    try:
        if not _check_permissions(config.item_edit):
            return resp("queue_in/get_sync/403/check_permissions", "you have no permissions for that")

        if not check_request_method(request, 'POST'):
            return resp("queue_in/get_sync/405/check_request_post", "Use POST at this URL")

        r_json = request.get_json()

        if not _check_request_ok(r_json):
            return resp("queue_in/get_sync/405/check_req", "Malformed JSON request")

        config.db.start_transaction("_get_sync")

        if not _check_revs(config, r_json):
            config.db.rollback_transaction()
            return resp("queue_in/get_sync/403/no_match_revs", "Revs don't match")

        got_shadow, shadow = _get_server_shadow(config, r_json)
        if not got_shadow:
            config.db.rollback_transaction()
            return resp("queue_in/get_sync/404/not_shadow", "Shadow not found. PUT the full shadow to URL + /shadow")

        if not check_crc(shadow, r_json['old_shadow_adler32']):
            config.db.rollback_transaction()
            return resp("queue_in/get_sync/403/check_crc_old", "CRC of old shadow doesn't match")

        # finally start patching:
        patch_ok, new_shadow = _patch_server_shadow(config, shadow)

        if not check_crc(new_shadow, r_json['shadow_adler32']):
            config.db.rollback_transaction()
            return resp("queue_in/get_sync/403/check_crc_new", "CRC of new shadow doesn't match")

        # if final check is done save shadow
        config.db.rollback_transaction()
        abort(500)  # 500 Internal Server Error

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/get_sync/500/transaction_exception", "Unknown error. Please report this")
    else:
        #####
        # FIXME: delete me:
        config.db.rollback_transaction()
        abort(404)
        ####
        config.db.end_transaction()
        return resp("queue_in/get_sync/201/ack", "Sync acknowledged")


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>/shadow', methods=['PUT'])
def _get_shadow(user_id, client_node_id, item_id):
    log.debug("got a request at /users/{}/nodes/{}/items/{}/shadow".format(user_id, client_node_id, item_id, ))
    config.item_edit = {"item_user_id": user_id, "item_node_id": client_node_id, "item_id": item_id}

    try:
        if not _check_permissions(config.item_edit):
            return resp("queue_in/get_shadow/403/check_permissions", "you have no permissions for that")

        if not check_request_method(request, 'PUT'):
            return resp("queue_in/get_shadow/405/check_request_put", "Use PUT at this URL")

        r_json = request.get_json()

        check_shadow_ok, shadow = _check_shadow_request_ok(r_json)
        if not check_shadow_ok:
            return resp("queue_in/get_shadow/405/check_req", "Malformed JSON request")

        log.debug("request with the shadow seems ok, trying to save it")
        config.db.start_transaction("_get_shadow")

        item_exists, item = _check_item_exists(item_id)
        if not item_exists:
            _save_item(item_id, shadow)

        _save_shadow(client_node_id, item_id, shadow, r_json['rev'], r_json['other_node_rev'])

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/get_shadow/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("_get_shadow about to finish OK")
        config.db.end_transaction()
        return resp("queue_in/get_sync/201/ack", "Sync acknowledged")


def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    # parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None
    return args.port, args.logginglevel


def _init():
    # import pdb; pdb.set_trace()
    client_port = 0
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


def prepare_data(new_text, old_shadow, old_shadow_adler32, shadow_adler32, shadow_client_rev, shadow_server_rev,
                 text_patches):
    base_data = {
        'create_date': firestore.SERVER_TIMESTAMP,
        'shadow_client_rev': shadow_client_rev,
        'shadow_server_rev': shadow_server_rev
    }
    shadow_data = dict(base_data)
    queue_data = dict(base_data)
    item_data = dict(base_data)
    shadow_data.update({
        'shadow': new_text,
        'old_shadow': old_shadow,  # FIXME check if this is really needed
    })
    queue_data.update({
        'text_patches': text_patches,
        'old_shadow_adler32': old_shadow_adler32,
        'shadow_adler32': shadow_adler32,
    })
    item_data.update({
        'text': new_text,
    })
    return item_data, queue_data, shadow_data


if __name__ == "__main__":  # pragma: no cover
    log.info("queue_in started")
    config = Config(node_id="node_2")
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
