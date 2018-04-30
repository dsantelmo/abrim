#!/usr/bin/env python

import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import logging
import os
import zlib
import hashlib
from pathlib import Path
import sqlite3

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from util import get_log, AbrimConfig
log = get_log(full_debug=False)



def get_item_ref(db, config, item_id):
    node_id = config.node_id
    try:
        db_prefix = config.db_prefix
    except AttributeError:
        db_prefix = ''
    db_path = db_prefix + 'nodes'

    # create new item
    item_text = "original text"

    node_ref = db.collection(db_path).document(node_id)
    return node_ref.collection('items').document(item_id)


def _get_shadow_revs_ref(item_ref, node_id):
    return item_ref.collection('shadows').document(node_id).collection('revs')


def get_queue_1_revs_ref(item_ref, node_id):
    return item_ref.collection('queue_1_to_process').document(node_id).collection('revs')


def _enqueue_client_edits(item_ref, new_text, old_shadow, shadow_client_rev, shadow_server_rev, transaction, node_id):
    shadow_client_rev += 1
    shadow_server_rev += 1
    text_patches = create_diff_edits(new_text, old_shadow)
    old_shadow_adler32 = _create_hash(old_shadow)
    shadow_adler32 = _create_hash(new_text)
    try:
        item_data, queue_data, shadow_data = prepare_data(new_text, old_shadow, old_shadow_adler32, shadow_adler32,
                                                          shadow_client_rev, shadow_server_rev, text_patches)

        log.debug("creating shadow, queue and saving item for node {}".format(node_id))
        shadow_ref = _get_shadow_revs_ref(item_ref, node_id).document(str(shadow_client_rev))
        queue_ref = get_queue_1_revs_ref(item_ref, node_id).document(str(shadow_client_rev))
        transaction.set(shadow_ref, shadow_data)
        transaction.set(queue_ref, queue_data)
        transaction.set(item_ref, item_data)

        log.debug('About to commit transaction...')
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        return False
    log.info('New update saved')
    return True


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


def update_item(config, item_id, new_text=""):
    config.db.start_transaction()

    config.db.save_item(item_id, new_text)

    # db = firestore.Client()
    # item_ref = get_item_ref(db, config, item_id)

    for other_node_id, _ in config.db.get_known_nodes():

        shadow_client_rev, shadow_server_rev, old_shadow = config.db.get_rev_shadow(other_node_id, item_id)

        # transaction = db.transaction()
        # result = update_in_transaction(config, transaction, item_ref, new_text, other_node_id, item_id)


    config.db.end_transaction()

    sys.exit(0)
    if result:
        log.debug('update transaction ended OK')
        return True
    else:
        log.error('ERROR updating item')
        raise Exception


if __name__ == "__main__":
    node_id = "node_1"
    config = AbrimConfig(node_id)
    config.db.add_known_node('node_2', "http://localhost:5002")

    log.debug("NODE ID: {}".format(config.node_id,))
    log.debug("db_path: {}".format(config.db.db_path))

    # item_id = uuid.uuid4().hex
    item_id = "item_1"

    update_item(config, item_id, "")
    update_item(config, item_id, "a new text")
    update_item(config, item_id, "a newer text")
    sys.exit(0)
