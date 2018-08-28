#!/usr/bin/env python

import traceback
import time
from flask import Flask, g, request, abort
from abrim.config import Config
from abrim.util import get_log, fragile_patch_text, resp, check_fields_in_dict, check_crc, get_crc, create_diff_edits, \
                       create_hash, args_init

log = get_log(full_debug=False)

app = Flask(__name__)


def _get_server_shadow(item_id, client_node_id, n_rev, m_rev):
    got_shadow, shadow = config.db.get_shadow(item_id, client_node_id, n_rev, m_rev)
    if got_shadow:
        log.debug("shadow: {}".format(shadow))
    return got_shadow, shadow


def _patch_server_shadow(edits, shadow):
    if edits == "" and shadow == "":
        log.debug("no shadow or patches, nothing to patch...")
        return "", True
    else:
        new_shadow, patch_success = fragile_patch_text(edits, shadow)
        if not patch_success:
            log.debug("patching failed")
            return "", False
        else:
            return new_shadow, patch_success


def _check_post_sync_request_ok(r_js):
    if not check_fields_in_dict(r_js, ('edits',)):
        log.debug("no edits")
    if not check_fields_in_dict(r_js, ('n_rev', 'm_rev', 'old_shadow_adler32', 'shadow_adler32',)):
        return None
    try:
        log.debug("n_rev: {} - m_rev: {}".format(r_js['n_rev'], r_js['m_rev']))
        log.debug("has edits: {:.30}...".format(r_js['edits'].replace('\n', ' ')))
    except KeyError:
        log.debug("edit request revs: {} - {}, no edits".format(r_js['shadow_client_rev'],
                                                               r_js['shadow_server_rev']))
    return r_js['n_rev'], r_js['m_rev'], r_js['old_shadow_adler32'], r_js['shadow_adler32'], r_js['edits']


def _check_shadow_request_ok(r_json):
    if not check_fields_in_dict(r_json, ('n_rev', 'm_rev', 'shadow',)):
        return False, _
    try:
        log.info("revs: {} - {}".format(r_json['n_rev'], r_json['m_rev']))
        log.info("has shadow: {:.30}...".format(r_json['shadow'].replace('\n', ' ')))
    except KeyError:
        log.error("no shadow in request")
        return False, _
    return True, r_json['shadow']


def _check_text_request_ok(r_json):
    if not check_fields_in_dict(r_json, ('text',)):
        return False, _
    try:
        log.debug("text: {:.30}...".format(r_json['text'].replace('\n', ' ')))
    except KeyError:
        log.error("no shadow in request")
        return False, _
    return True, r_json['text']


def _check_revs(item_id, client_node_id, n_rev, m_rev):
    saved_n_rev, saved_m_rev = config.db.get_latest_revs(item_id, client_node_id)

    if n_rev != saved_n_rev:
        log.error("n_rev DOESN'T match: {} - {}".format(n_rev, saved_n_rev))
        return False
    if m_rev != saved_m_rev:
        log.error("m_rev DOESN'T match: {} - {}".format(m_rev, saved_m_rev))
        return False
    return saved_n_rev, saved_m_rev


def _check_permissions(dummy):  # TODO: implement me
    return True


def _check_item_exists(item_id):
    return config.db.get_item(item_id)


def _save_shadow(client_node_id, item_id, shadow, n_rev, m_rev, crc):
    config.db.save_new_shadow(client_node_id, item_id, shadow, n_rev, m_rev, crc)


def _enqueue_patches(client_node_id, item_id, patches, n_rev, m_rev, old_crc, new_crc):
    config.db.save_new_patches(client_node_id, item_id, patches, n_rev, m_rev, old_crc, new_crc)


def _check_patch_done(timeout, client_node_id, item_id, n_rev, m_rev):
    # wait a bit for the patching of server text
    while True:
        patch_done = config.db.check_if_patch_done(client_node_id, item_id, n_rev, m_rev)
        if patch_done:
            break
        else:
            if timeout < 0:
                log.warn("server didn't processed the patch within the allotted time. Possible server overload")
                return None
            time.sleep(1)
            timeout -= 1

    patch_done = {'json': 'response_all_ok_and_new_edits_for_client'} # fixme: delete me
    return patch_done


def update_item(config, item_id, new_text):
    config.db.save_item(item_id, new_text, get_crc(new_text))
    for other_node_id, _ in config.db.get_known_nodes():
        n_rev, m_rev, old_shadow = config.db.get_latest_rev_shadow(other_node_id, item_id)
        n_rev += 1
        config.db.save_new_shadow(other_node_id, item_id, new_text, n_rev, m_rev, get_crc(new_text))
        diffs = create_diff_edits(new_text, old_shadow)  # maybe doing a slow blocking diff in a transaction is wrong
        if n_rev == 0 or diffs:
            old_hash = create_hash(old_shadow)
            new_hash = create_hash(new_text)
            log.debug("old_hash: {}, new_hash: {}, diffs: {}".format(old_hash, new_hash, diffs))
            config.db.enqueue_client_edits(other_node_id, item_id, diffs, old_hash, new_hash, n_rev, m_rev)
        else:
            log.warn("no diffs. Nothing done!")


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['POST'])
def _post_sync(user_id, client_node_id, item_id):
    log.debug("-------------------------------------------------------------------------------")
    log.debug("POST REQUEST: /users/{}/nodes/{}/items/{}".format(user_id, client_node_id, item_id, ))

    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/post_sync/403/check_permissions", "you have no permissions for that")

        r_json = request.get_json()

        try:
            n_rev, m_rev, old_shadow_adler32, shadow_adler32, edits = _check_post_sync_request_ok(r_json)
        except TypeError:
            return resp("queue_in/post_sync/405/check_req", "Malformed JSON request")

        config.db.start_transaction("_post_sync")

        if not _check_revs(item_id, client_node_id, n_rev, m_rev):
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/403/no_match_revs", "Revs don't match")

        got_shadow, shadow = _get_server_shadow(item_id, client_node_id, n_rev, m_rev)
        if not got_shadow:
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/404/not_shadow", "Shadow not found. PUT the full shadow to URL + /shadow")

        if not check_crc(shadow, old_shadow_adler32):
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/403/check_crc_old", "CRC of old shadow doesn't match")

        new_shadow, patch_success = _patch_server_shadow(edits, shadow)

        if not patch_success:
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/500/shadow_patch_unsuccessful", "Failed to patch shadow")

        if not check_crc(new_shadow, shadow_adler32):
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/403/check_crc_new", "CRC of new shadow doesn't match")

        n_rev += 1

        _save_shadow(client_node_id, item_id, new_shadow, n_rev, m_rev, shadow_adler32)

        _enqueue_patches(client_node_id, item_id, edits, n_rev, m_rev, old_shadow_adler32, shadow_adler32)

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/post_sync/500/transaction_exception", "Unknown error. Please report this")
    else:
        config.db.end_transaction()

    timeout = 5
    patch_done_json = _check_patch_done(timeout, client_node_id, item_id, n_rev, m_rev)
    if not patch_done_json:
        return resp("queue_in/post_sync/201/ack", "Sync acknowledged. Still waiting for patch to apply")
    return resp("queue_in/post_sync/201/done", "Sync done", patch_done_json)


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>/shadow', methods=['PUT'])
def _put_shadow(user_id, client_node_id, item_id):
    log.debug("-------------------------------------------------------------------------------")
    log.debug("PUT REQUEST: /users/{}/nodes/{}/items/{}/shadow".format(user_id, client_node_id, item_id, ))
    config.item_edit = {"item_user_id": user_id, "item_node_id": client_node_id, "item_id": item_id}

    try:
        if not _check_permissions(config.item_edit):
            return resp("queue_in/put_shadow/403/check_permissions", "you have no permissions for that")

        r_json = request.get_json()

        check_shadow_ok, shadow = _check_shadow_request_ok(r_json)
        if not check_shadow_ok:
            return resp("queue_in/put_shadow/405/check_req", "Malformed JSON request")

        log.debug("request with the shadow seems ok, trying to save it")
        config.db.start_transaction("_put_shadow")

        item_exists, item, _ = _check_item_exists(item_id)
        if not item_exists:
            # _save_item(item_id, shadow)
            update_item(config, item_id, shadow)

        else:
            _save_shadow(client_node_id, item_id, shadow, r_json['n_rev'], r_json['m_rev'], get_crc(shadow))

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/put_shadow/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("_put_shadow about to finish OK")
        config.db.end_transaction()
        return resp("queue_in/put_shadow/201/ack", "Sync acknowledged")


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['GET'])
def _get_text(user_id, client_node_id, item_id):
    config = g.config
    log.debug("-------------------------------------------------------------------------------")
    log.debug("GET REQUEST: /users/{}/nodes/{}/items/{}".format(user_id, client_node_id, item_id, ))

    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/get_text/403/check_permissions", "you have no permissions for that")

        item_ok, item_text, item_crc = config.db.get_item(item_id)

        if not item_ok:
            return resp("queue_in/get_text/404/not_item", "Item not found")

    except Exception as err:
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/get_text/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("get_text about to finish OK")
        return resp("queue_in/get_text/200/ok", "get_text OK", {"text": item_text, "crc": item_crc})


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['PUT'])
def _put_text(user_id, client_node_id, item_id):
    log.debug("-------------------------------------------------------------------------------")
    log.debug("PUT REQUEST: /users/{}/nodes/{}/items/{}".format(user_id, client_node_id, item_id, ))

    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/put_text/403/check_permissions", "you have no permissions for that")

        r_json = request.get_json()

        check_text_ok, new_text = _check_text_request_ok(r_json)
        if not check_text_ok:
            return resp("queue_in/put_text/405/check_req", "Malformed JSON request")

        log.debug("request with the text seems ok, trying to save it")
        config.db.start_transaction("_put_text")

        update_item(config, item_id, new_text)

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/put_text/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("_put_text about to finish OK")
        config.db.end_transaction()
    return resp("queue_in/put_text/200/ok", "PUT OK")


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items', methods=['GET'])
def _get_items(user_id, client_node_id):
    log.debug("-------------------------------------------------------------------------------")
    log.debug("GET REQUEST: /users/{}/nodes/{}/items".format(user_id, client_node_id))

    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/get_items/403/check_permissions", "you have no permissions for that")

        # config.db.sql_debug_trace(True)
        items = config.db.get_items()
        if not items:
            return resp("queue_in/get_items/404/not_items", "No items")

    except Exception as err:
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/get_items/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("get_text about to finish OK")
        return resp("queue_in/get_items/200/ok", "get_text OK", items)


def __end():
    # db.close_db()
    pass


@app.before_request
def before_request():
    # db.prepare_db_path(app.config['DB_PATH'])
    config = Config(node_id=app.config['NODE_ID'])
    g.config = config
    #pass


@app.teardown_request
def teardown_request(exception):
    __end()


if __name__ == "__main__":  # pragma: no cover
    log.info("queue_in started")
    node_id, client_port = args_init()
    if 'NODE_ID' not in app.config:
        app.config['NODE_ID'] = node_id
    # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    # app.run(host='0.0.0.0', port=client_port)
    # for pycharm debugging
    app.run(host='0.0.0.0', port=client_port, debug=True, use_debugger=False, use_reloader=False)
    __end()
