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
from abrim.util import get_log, patch_text, resp


log = get_log(full_debug=False)

app = Flask(__name__)


# # to avoid race conditions existence of the item and creation should be done in a transaction
# @firestore.transactional
# def create_in_transaction(transaction, item_ref, item_rev, item_create_date):
#     try:
#         try:
#             item_exist = item_ref.get(transaction=transaction)
#
#             log.error("Tried to create the item but it's already been created")
#             return False  # it shouldn't be there
#         except google.api.core.exceptions.NotFound:
#             transaction.set(item_ref, {
#                 'other_node_create_date': item_create_date,
#                 'client_rev': item_rev,
#             })
#     except (grpc._channel._Rendezvous,
#             google.auth.exceptions.TransportError,
#             google.gax.errors.GaxError,
#             ):
#         log.error("Connection error to Firestore")
#         return False
#     log.debug("creation enqueued correctly")
#                 'create_date': firestore.SERVER_TIMESTAMP,
#     return True


# def server_create_item(config):
#     log.debug("server_create_item transaction")
#
#     node_id = config.node_id
#     item_node_id = config.item_node_id
#     item_id = config.item_id
#     item_rev = config.item_rev
#     item_create_date = config.item_create_date
#
#     db = firestore.Client()
#     server_node_ref = db.collection('nodes').document(node_id)
#     other_node_ref = server_node_ref.collection('other_nodes').document(item_node_id)
#     item_ref = other_node_ref.collection('items').document(item_id)
#
#     transaction = db.transaction()
#
#     log.debug("trying to create /nodes/{}/other_nodes/{}/items/{}".format(node_id,item_node_id,item_id,))
#
#     result = create_in_transaction(transaction, item_ref, item_rev, item_create_date)
#     if result:
#         log.debug('transaction ended OK')
#         return True
#     else:
#         log.error('ERROR saving new item')
#         return False


# def _check_item_patch_exist(transaction, item_ref, item_rev):
#     try:
#         _ = item_ref.get(transaction=transaction)
#         # exists so we can continue
#     except google.api.core.exceptions.NotFound:
#         log.error("ERROR item to patch doesn't exist")
#         return False  # it doesn't exists
#     try:
#         patches_ref = item_ref.collection('patches').document(str(item_rev))
#         _ = patches_ref.get(transaction=transaction)
#         log.error("ERROR patch already exists")
#         return False  # it shouldn't be there
#     except google.api.core.exceptions.NotFound:
#         return True


def _get_shadow_dict(transaction, item_ref, item_node_id):
    log.debug("shadow_ref: (item_ref)/shadows/{}".format(item_node_id,))
    shadow_ref = item_ref.collection('shadows').document(item_node_id)
    try:
        try:
            item = shadow_ref.get(transaction=transaction).to_dict()
            log.debug("shadow exists: {}".format(item))
            return item
        except google.api.core.exceptions.NotFound:
            log.debug("creating new empty shadow")
            _, _, shadow_data = prepare_data("", "", None, None, 0, 0, None)
            transaction.set(shadow_ref, shadow_data)
            return shadow_data
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        raise


def _get_shadow_and_revs(transaction, item_ref, item_node_id):
    # /nodes/node_1/items/item_1/shadows/node_2/revs
    log.debug("getting shadow for {}".format(item_node_id))
    shadow_dict = _get_shadow_dict(transaction, item_ref, item_node_id)
    log.debug("item: {}".format(shadow_dict))

    try:
        shadow = shadow_dict['shadow']
    except KeyError:
        shadow = ''
    try:
        stored_server_rev = shadow_dict['shadow_server_rev']
        stored_client_rev = shadow_dict['shadow_client_rev']
    except KeyError:
        log.error("KeyError with client_rev")
        return False
    return shadow, stored_server_rev, stored_client_rev


# to avoid race conditions existence of the item and creation should be done in a transaction
@firestore.transactional
def enqueue_update_in_transaction(transaction, item_ref, config):
    try:
        test_shadow = zlib.adler32(shadow.encode())
        if config.old_shadow_adler32 != test_shadow:
            log.error("shadows adler32s don't match {} {}".format(config.old_shadow_adler32, test_shadow,))
            return False

        if config.edits == "" and shadow == "":
            log.debug("no shadow or patches, nothing to patch...")
            new_item_shadow = ""
        else:
            new_item_shadow, success = patch_text(config.edits, shadow)
            if not success:
                log.debug("patching failed")
                return False

        test_shadow = zlib.adler32(new_item_shadow.encode())
        if config.shadow_adler32 != test_shadow:
            log.error("new shadows adler32s don't match {} {}".format(config.shadow_adler32, test_shadow,))
            return False

        # TODO: think in maybe save the CRC to avoid recalculating but it makes more complex updating the DB by hand...

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


def _get_server_shadow(config):
    i_e = config.item_edit
    shadow = config.db.get_shadow(i_e['item_id'],
                                  i_e['item_node_id'],
                                  i_e['shadow_server_rev'],
                                  i_e['shadow_client_rev'])
    if shadow:
        log.debug("shadow: {}".format(shadow))
    else:
        return False


def _patch_server_shadow(config, shadow):
    # config.db.save_new_shadow(i_e['item_node_id'],
    #                           i_e['item_id'],
    #                           shadow,
    #                           i_e['shadow_server_rev'],
    #                           i_e['shadow_client_rev']
    #                           )
    log.error("unknown error")
    return False


@app.errorhandler(405)
def errorhandler405(e):
    return Response('405', 405, {'Allow':'POST'})


def parse_req(i_e, r_j):
    log.debug("parse_req: {}".format(r_j))
    try:
        i_e['shadow_client_rev'] = r_j['rev']
        i_e['shadow_server_rev'] = r_j['other_node_rev']
    except KeyError:
        log.error("rev or create_date")
        log.error("HTTP 400 Bad Request")
        abort(400)

    try:
        edits = r_j['edits']
        if edits:
            i_e['edits'] = r_j['edits']
    except KeyError:
        log.debug("no edits")

    try:
        i_e['old_shadow_adler32'] = r_j['old_shadow_adler32']
        i_e['shadow_adler32'] = r_j['shadow_adler32']
    except KeyError:
        log.error("missing old_shadow_adler32 or shadow_adler32")
        log.error("HTTP 400 Bad Request")
        abort(400)


def _check_request_ok(i_e, request):
    if request.method == 'POST':
        parse_req(i_e, request.get_json())

        log.info("edit request: {}/{}/{}".format(i_e['item_user_id'],
                                                 i_e['item_node_id'],
                                                 i_e['item_id']
                                                 ))
        try:
            log.info("edit request revs: {} - {}, has edits: {:.30}...".format(i_e['shadow_client_rev'],
                                                                               i_e['shadow_server_rev'],
                                                                               i_e['edits'].replace('\n', ' ')
                                                                               ))
        except KeyError:
            log.info("edit request revs: {} - {}, no edits".format(i_e['shadow_client_rev'],
                                                                   i_e['shadow_server_rev'],
                                                                   ))
        # x = 0
        # for item in config.item_edit.items():
        #     x += 1
        #     log.debug("{}. {}: {} ({})".format(x, item[0],item[1],type(item[1])))
        # x = 0
        # for item in vars(config).items():
        #     x += 1
        #     log.debug("{}. {}: {} ({})".format(x, item[0],item[1],type(item[1])))
        return True
    else:
        return False


def _check_revs(config):
    i_e = config.item_edit
    saved_rev, saved_other_node_rev = config.db.get_revs(i_e['item_id'], i_e['item_node_id'])

    if i_e['shadow_client_rev'] == saved_other_node_rev:
        log.debug("client revs match")
    else:
        log.error("client revs DON'T match")
        log.error("{} - {}".format(i_e['shadow_client_rev'], saved_other_node_rev))
        return False

    if config.item_edit['shadow_server_rev'] == saved_rev:
        log.debug("server revs match")
    else:
        log.error("server revs DON'T match")
        log.error("{} - {}".format(i_e['shadow_server_rev'], saved_other_node_rev))
        return False

    return saved_rev, saved_other_node_rev


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['POST'])
def _get_sync(user_id, client_node_id, item_id):
    log.debug("got a request at /users/{}/nodes/{}/items/{}".format(user_id, client_node_id, item_id, ))

    config.item_edit = {"item_user_id": user_id,
                        "item_node_id": client_node_id,
                        "item_id": item_id
                        }

    if _check_request_ok(config.item_edit, request):
        try:
            config.db.start_transaction("_get_sync")
            if not _check_revs(config):
                return resp(404, 'ERR_PROCESS', "queue_in-_get_sync-not_check_revs", "Revs don't check")

            shadow = _get_server_shadow(config)
            if not shadow:
                return resp(404, 'ERR_NO_SHADOW', "queue_in-_get_sync-not_shadow", "Shadow not found. Please send the full item")

            if not _patch_server_shadow(config, shadow):
                abort(500)  # 500 Internal Server Error

        except Exception as err:
            config.db.rollback_transaction()
            log.error(err)
            traceback.print_exc()
            return resp(500, 'ERR_UNKNOWN', "queue_in-_get_sync-exception", "Unknown error. Please report this")
        else:
            config.db.end_transaction()
            # FIXME: delete me:
            abort(404)
            return resp(201, 'OK_SYNC', "queue_in-_get_sync-ok", "Sync acknowledged")


    else:
        log.debug("HTTP 405 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(405)  # 405 Method Not Allowed


def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    # parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None
    return args.port, args.logginglevel #, args.initdb


def _init():
    #import pdb; pdb.set_trace()
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
