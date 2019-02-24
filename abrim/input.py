#!/usr/bin/env python

import traceback
import time
import werkzeug
from flask import Flask, g, request
from abrim.config import Config
from abrim.util import get_log, fragile_patch_text, resp, check_fields_in_dict, check_crc, get_crc, create_diff_edits, \
                       create_hash, args_init, requires_auth

log = get_log(full_debug=False)

app = Flask(__name__)


def _get_server_shadow(config, item_id, client_node_id, n_rev, m_rev):
    got_shadow, shadow = config.db.get_shadow(item_id, client_node_id, n_rev, m_rev)
    if got_shadow:
        log.debug(f"shadow: {shadow}")
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
    # {'rowid': 1, 'item': 'item_id_01', 'other_node': '<id>', 'n_rev': 0, 'm_rev': 0, 'edits': '@@ -0,0 +1,6 @@\n+all ok\n', 'hash': '1'}
    if not check_fields_in_dict(r_js, ('edits',)):
        log.debug("no edits")
    if not check_fields_in_dict(r_js, ('n_rev', 'm_rev', 'hash',)):
        return None
    try:
        log.debug(f"n_rev: {r_js['n_rev']} - m_rev: {r_js['m_rev']}")
        log.debug("has edits: {:.30}...".format(r_js['edits'].replace('\n', ' ')))
    except KeyError:
        log.debug(f"wrongly formated sync request: {r_js}")
    return r_js['n_rev'], r_js['m_rev'], r_js['hash'], r_js['edits']


def _check_shadow_request_ok(r_json):
    if not check_fields_in_dict(r_json, ('n_rev', 'm_rev', 'shadow',)):
        return False, _
    try:
        log.info(f"revs: {r_json['n_rev']} - {r_json['m_rev']}")
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
        log.error("no text in request")
        return False, _
    return True, r_json['text']


def _check_new_node_ok(r_json):
    if not check_fields_in_dict(r_json, ('new_node_base_url',)):
        return False, _
    try:
        log.debug("new_node_base_url: {:.30}...".format(r_json['new_node_base_url'].replace('\n', ' ')))
    except KeyError:
        log.error("no new_node_base_url in request")
        return False, _
    return True, r_json['new_node_base_url']


def _check_permissions(dummy):  # TODO: implement me
    return True


def _check_item_exists(config, item_id):
    return config.db.get_item(item_id)


def _save_shadow(config, client_node_id, item_id, shadow, n_rev, m_rev, crc):
    config.db.save_new_shadow(client_node_id, item_id, shadow, n_rev, m_rev, crc)


def _enqueue_patches(config, client_node_id, item_id, patches, n_rev, m_rev, crc):
    config.db.save_new_patches(client_node_id, item_id, patches, n_rev, m_rev, crc)


def _check_patch_done(config, timeout, client_node_id, item_id, n_rev, m_rev):
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
    log.debug(f"saving item {item_id} with {new_text}")
    new_text_crc = get_crc(new_text)
    config.db.update_item(item_id, new_text, new_text_crc)
    for known_node in config.db.get_known_nodes():
        other_node_id = known_node["id"]

        n_rev, m_rev, old_shadow = config.db.get_latest_rev_shadow(other_node_id, item_id)

        log.debug(f"latest revs for that item in {other_node_id} are {n_rev} - {m_rev}")
        log.debug(f"creating diffs")
        diffs = create_diff_edits(new_text, old_shadow)  # maybe doing a slow blocking diff in a transaction is wrong
        if diffs:
            _enqueue_edit(config, other_node_id, item_id, diffs, n_rev, m_rev, old_shadow)

            # now save the new shadow for the other node
            n_rev += 1
            log.debug(f"saving new shadow for {other_node_id} with crc {new_text_crc}")
            config.db.save_new_shadow(other_node_id, item_id, new_text, n_rev, m_rev, new_text_crc)
        else:
            log.warning("no diffs. Nothing done!")


@app.route('/auth', methods=['GET'])
@requires_auth
def _auth():
    log.debug("_auth")
    if not _check_permissions("to do"):  # TODO: implement me
        return resp("queue_in/auth/403/check_permissions", "you have no permissions for that")
    else:
        return resp("queue_in/auth/200/ok", "auth OK")


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>', methods=['POST'])
@requires_auth
def _post_sync(user_id, client_node_id, item_id):
    log.debug("_post_sync")
    config = g.config
    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/post_sync/403/check_permissions", "you have no permissions for that")

        r_json = request.get_json()

        try:
            n_rev, m_rev, hash_, edits = _check_post_sync_request_ok(r_json)
        except TypeError:
            return resp("queue_in/post_sync/405/check_req", "Malformed JSON request")

        config.db.start_transaction("_post_sync")

        saved_n_rev, saved_m_rev = config.db.get_latest_revs(item_id, client_node_id)

        if not saved_n_rev and not saved_m_rev:
            # it's a new item, so create a new empty shadow
            saved_n_rev = 0
            saved_m_rev = 0
            _save_shadow(config, client_node_id, item_id, "", saved_n_rev, saved_m_rev, 1)

        if n_rev != saved_n_rev:
            if n_rev < saved_n_rev:
                log.warn(f"n_rev DOESN'T match: {n_rev} < {saved_n_rev}")
                if config.db.find_rev_shadow(client_node_id, item_id, n_rev, m_rev, old_shadow_adler32):
                    # lost return packet
                    # FIXME: we should delete local edits at this point
                    # copy backup shadow to shadow (in our code that means deleting shadows with a higher than n_rev)
                    config.db.delete_revs_higher_than(client_node_id, item_id, n_rev)
                    config.db.end_transaction()
                    return resp("queue_in/post_sync/201/lost_return_packet", "Accepted, but that looked like you lost a return packet from me")
                else:
                    config.db.rollback_transaction()
                    raise Exception("implement me! 1")
            else:
                log.warn(f"n_rev DOESN'T match: {n_rev} > {saved_n_rev}")
                config.db.rollback_transaction()
                raise Exception("implement me! 2")
            # return resp("queue_in/post_sync/403/no_match_revs", "Revs don't match")
        if m_rev != saved_m_rev:
            log.error(f"m_rev DOESN'T match: {m_rev} != {saved_m_rev}")
            config.db.rollback_transaction()
            raise Exception("implement me! 3")

        got_shadow, shadow = _get_server_shadow(config, item_id, client_node_id, n_rev, m_rev)

        if not got_shadow:
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/404/not_shadow", "Shadow not found. PUT the full shadow to URL + /shadow")
        if not check_crc(shadow, hash_):
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/403/check_crc", "CRC of shadow doesn't match")

        new_shadow, patch_success = _patch_server_shadow(edits, shadow)

        if not patch_success:
            config.db.rollback_transaction()
            return resp("queue_in/post_sync/500/shadow_patch_unsuccessful", "Failed to patch shadow")
        else:
            _enqueue_patches(config, client_node_id, item_id, edits, n_rev, m_rev, hash_) # save patches to patch queue
            n_rev += 1
            new_hash = get_crc(new_shadow)
            _save_shadow(config, client_node_id, item_id, new_shadow, n_rev, m_rev, new_hash) # save new shadow

    except Exception as err:
        config.db.rollback_transaction()
        log.error(f"ERROR: {err}")
        traceback.print_exc()
        return resp("queue_in/post_sync/500/transaction_exception", "Unknown error. Please report this")
    else:
        config.db.end_transaction()

    timeout = 5
    patch_done_json = _check_patch_done(config, timeout, client_node_id, item_id, n_rev, m_rev)
    if not patch_done_json:
        return resp("queue_in/post_sync/201/ack", "Sync acknowledged. Still waiting for patch to apply")
    return resp("queue_in/post_sync/201/done", "Sync done", patch_done_json)


@app.route('/users/<string:user_id>/nodes/<string:client_node_id>/items/<string:item_id>/shadow', methods=['PUT'])
@requires_auth
def _put_shadow(user_id, client_node_id, item_id):
    log.debug("_put_shadow")
    config = g.config
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

        item_exists, item, _ = _check_item_exists(config, item_id)
        if not item_exists:
            # _save_item(item_id, shadow)
            update_item(config, item_id, shadow)

        else:
            _save_shadow(config, client_node_id, item_id, shadow, r_json['n_rev'], r_json['m_rev'], get_crc(shadow))

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
@requires_auth
def _get_text(user_id, client_node_id, item_id):
    log.debug("_get_text")
    config = g.config
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
@requires_auth
def _put_text(user_id, client_node_id, item_id):
    log.debug("_put_text")
    config = g.config
    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/put_text/403/check_permissions", "you have no permissions for that")

        try:
            r_json = request.get_json()
        except werkzeug.exceptions.BadRequest:
            return resp("queue_in/put_text/405/check_req", "Malformed JSON request")

        check_text_ok, new_text = _check_text_request_ok(r_json)
        if not check_text_ok:
            return resp("queue_in/put_text/405/check_req", "Malformed JSON request")

        log.debug("request with the text seems ok, trying to save it")
        config.db.start_transaction("_put_text")
        item_exists, item, _ = _check_item_exists(config, item_id)

        if item_exists:
            # update_item(config, item_id, new_text)
            config.db.end_transaction()
            return resp("queue_in/put_text/200/item_exists", "ITEM EXISTS")
        else:
            new_item(config, item_id, new_text)

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
@requires_auth
def _get_items(user_id, client_node_id):
    log.debug("_get_items")
    config = g.config
    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/get_items/403/check_permissions", "you have no permissions for that")

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


@app.route('/users/<string:user_id>/nodes', methods=['GET'])
@requires_auth
def _get_nodes(user_id):
    log.debug("_get_nodes")
    config = g.config
    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/get_nodes/403/check_permissions", "you have no permissions for that")

        nodes = config.db.get_known_nodes()
        if not nodes:
            return resp("queue_in/get_nodes/404/not_items", "No nodes")

    except Exception as err:
        log.error(err)
        traceback.print_exc()
        return resp("queue_in/get_nodes/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("get_nodes about to finish OK")
        return resp("queue_in/get_nodes/200/ok", "get_nodes OK", nodes)


@app.route('/users/<string:user_id>/nodes', methods=['POST'])
@requires_auth
def _post_node(user_id):
    log.debug("_post_node")
    config = g.config
    try:
        if not _check_permissions("to do"):  # TODO: implement me
            return resp("queue_in/post_node/403/check_permissions", "you have no permissions for that")

        try:
            r_json = request.get_json()
        except werkzeug.exceptions.BadRequest:
            return resp("queue_in/post_node/405/check_req", "Malformed JSON request")

        check_new_node_ok, new_node_base_url = _check_new_node_ok(r_json)
        if not check_new_node_ok:
            return resp("queue_in/post_node/405/check_req", "Malformed JSON request")

        log.debug("request with the new node seems ok, trying to save it")
        config.db.start_transaction("_post_node")

        node_uuid = config.db.add_known_node(new_node_base_url)
    except Exception as err:
        config.db.rollback_transaction()
        log.error(f"ERROR: {err}")
        traceback.print_exc()
        return resp("queue_in/post_node/500/transaction_exception", "Unknown error. Please report this")
    else:
        log.info("_post_node about to finish OK")
        config.db.end_transaction()

    return resp("queue_in/post_node/201/done", f"{node_uuid}")




def __end():
    # db.close_db()
    pass


@app.before_request
def before_request():
    log.debug("-------------------------------------------------------------------------------")
    if request.full_path and request.method:
        log.debug(f"{request.method} REQUEST: {request.full_path}")
        if request.data:
            log.debug(f"{request.method} REQUEST HAS DATA: {request.data}")
    else:
        log.error("request doesn't have a full_path and/or method")
        return resp("queue_in/before_request/500/unknown", "Unknown error. Please report this")
    # db.prepare_db_path(app.config['DB_PATH'])
    config = Config(app.config['NODE_ID'], app.config['PORT'])
    g.config = config


@app.teardown_request
def teardown_request(exception):
    __end()


if __name__ == "__main__":  # pragma: no cover
    log.info(f"{__file__} started")
    node_id, client_port = args_init()

    if not node_id or not client_port:
        __end()
    else:
        log.info(f"node {node_id} running in port {client_port}")
        if 'NODE_ID' not in app.config:
            app.config['NODE_ID'] = node_id
        if 'PORT' not in app.config:
            app.config['PORT'] = client_port
        # app.run(host='0.0.0.0', port=client_port, use_reloader=False)
        # app.run(host='0.0.0.0', port=client_port)
        # for pycharm debugging
        app.run(host='0.0.0.0', port=client_port, debug=False, use_debugger=False, use_reloader=False)
        __end()
