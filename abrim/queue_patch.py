#!/usr/bin/env python

import logging
import multiprocessing
import os
import sys
import time
import zlib

import diff_match_patch
import google
import grpc
from google.cloud import firestore

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from node import AbrimConfig, create_item, create_diff_edits

full_debug = False
if full_debug:
    # enable debug for HTTP requests
    import http.client as http_client

    http_client.HTTPConnection.debuglevel = 1
else:
    # disable more with
    # for key in logging.Logger.manager.loggerDict:
    #    print(key)
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('google').setLevel(logging.CRITICAL)

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


@firestore.transactional
def try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before, new_text, client_rev,
                       other_node_create_date, create_date, item_id):
    try:
        try:
            new_item = new_item_ref.get().to_dict()
            log.debug("try_to_apply_patch::new_item: {}".format(new_item))
            try:
                old_text_now = new_item['text']
                if not old_text_before:
                    raise KeyError
            except KeyError:
                log.debug("error getting existing text! I'm going to assume is a newly create item and continue...")
                old_text_now = ""
        except google.api.core.exceptions.NotFound:
            old_text_now = ""
        if old_text_now == old_text_before:
            patches_deleted_ref = other_node_item_ref.collection('patches_deleted').document(str(patch_ref.id))

            # create edits
            text_patches = create_diff_edits(new_text, old_text_before)
            old_shadow_adler32 = zlib.adler32(old_text_before.encode())
            shadow_adler32 = zlib.adler32(new_text.encode())
            log.debug("old_shadow_adler32 {}".format(old_shadow_adler32))
            log.debug("shadow_adler32 {}".format(shadow_adler32))
            # old_shadow_sha512 = hashlib.sha512(old_shadow.encode()).hexdigest()
            # shadow_sha512 = hashlib.sha512(new_text.encode()).hexdigest()
            # log.debug("old_shadow_sha512 {}".format(old_shadow_sha512))
            # log.debug("shadow_sha512 {}".format(shadow_sha512))

            # prepare the update of shadow and client text revision
            try:
                transaction.update(new_item_ref, {
                    'last_update_date': firestore.SERVER_TIMESTAMP,
                    'text': new_text,
                    'shadow': new_text,
                    'client_rev': client_rev,
                })
                # queue_ref = new_item_ref.collection('queue_1_to_process').document(str(client_rev))
                # transaction.set(queue_ref, {
                #     'create_date': firestore.SERVER_TIMESTAMP,
                #     'client_rev': client_rev,
                #     'action': 'edit_item',
                #     'text_patches': text_patches,
                #     'old_shadow_adler32': old_shadow_adler32,
                #     'shadow_adler32': shadow_adler32,
                # })
            except (grpc._channel._Rendezvous,
                    google.auth.exceptions.TransportError,
                    google.gax.errors.GaxError,
                    ):
                log.error("Connection error to Firestore")
                return False
            log.info("server text patched!")

            # FIXME save the patch here
            transaction.set(patches_deleted_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
            })
            log.debug("patch archived")
            transaction.delete(patch_ref)
            log.debug("original patch deleted")

            return True
        else:
            log.debug("server text changed. Discarding...")
            return False
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        raise Exception


def server_patch_queue():
    # log.debug("starting server_patch_queue")
    node_id = "node_2"
    other_node_id = "node_1"

    db = firestore.Client()
    other_nodes_ref = db.collection('nodes').document(node_id).collection('other_nodes')
    for other_node in other_nodes_ref.get():
        # log.debug("processing patch queue from node {}".format(other_node.id))
        items_ref = other_nodes_ref.document(str(other_node.id)).collection('items')
        for item in items_ref.get():
            # log.debug("processing patches from item {}".format(item.id))
            other_node_item_ref = items_ref.document(item.id)
            patches_ref = other_node_item_ref.collection('patches')
            for patch in patches_ref.order_by('client_rev').get():
                log.debug("processing patch {}".format(patch.id))
                patch_ref = patches_ref.document(str(patch.id))
                patch_dict = patch_ref.get().to_dict()
                log.debug(patch_dict)
                try:
                    patches = patch_dict['patches']
                    client_rev = patch_dict['client_rev']
                    other_node_create_date = patch_dict['other_node_create_date']
                    create_date = patch_dict['create_date']
                except KeyError:
                    log.error("KeyError in patch. Wait 5 seconds")
                    time.sleep(5)
                    return False

                # now we should get the server text and try to fuzzy apply the patch to it
                # if the patch fails discard the patch
                # if the patch works and server text has not changed, atomically accept the patch and change the text
                # if the server text has changed after the patch repeat the process
                new_items_ref = db.collection('nodes').document(node_id).collection('items')
                new_item_ref = new_items_ref.document(str(item.id))
                try:
                    new_item_dict = new_item_ref.get().to_dict()
                    log.debug("node {} item {} exists".format(node_id, item.id))
                    try:
                        old_text_before = new_item_dict['text']
                        if not old_text_before:
                            raise KeyError
                    except KeyError:
                        old_text_before = ""
                except google.api.core.exceptions.NotFound:
                    log.debug("node {} item {} doesn't exist".format(node_id, item.id))

                    config = AbrimConfig("node_2")
                    create_item(config, str(item.id))
                    old_text_before = ""

                diff_obj = diff_match_patch.diff_match_patch()
                # these are FUZZY patches and mustn't match perfectly
                diff_match_patch.Match_Threshold = 1
                try:
                    log.debug("about to patch this: {}".format(patches))
                    patches_obj = diff_obj.patch_fromText(patches)
                except ValueError as ve:
                    log.error(ve)
                    return

                new_text, success = diff_obj.patch_apply(patches_obj, old_text_before)
                log.debug(new_text)
                log.debug(success)

                if not success:
                    log.debug("Patch failed. I should discard the patch")  # FIXME
                    time.sleep(100)

                transaction = db.transaction()
                result = try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before,
                                            new_text, client_rev, other_node_create_date, create_date, str(item.id))
                if result:
                    log.info("one patch was correctly processed")
                else:
                    log.info("Not patched! waiting 2 additional seconds")
                    time.sleep(2)


if __name__ == '__main__':

    db = firestore.Client()
    node_ref = db.collection('nodes').document("node_2")

    node_ref.set({
        'a': 'a'
    })

    this_item_ref = node_ref.collection('items').document("item_1")
    this_item_ref.set({
        "client_rev": 0,
        "last_update_date": firestore.SERVER_TIMESTAMP,
        "shadow": None,
        "text": None
    })

    other_node_ref = node_ref.collection('other_nodes').document("node_1")
    other_node_ref.set({
        'a': 'a'
    })

    item_ref = other_node_ref.collection('items').document("item_1")
    item_ref.set({
        "client_rev": 2,
        "last_update_date": firestore.SERVER_TIMESTAMP,
        "shadow": "a newer text"
    })

    patches_1_ref = item_ref.collection('patches').document("1")
    patches_1_ref.set({
        "client_rev": 1,
        "create_date": firestore.SERVER_TIMESTAMP,
        "other_node_create_date": firestore.SERVER_TIMESTAMP,
        "patches": '@@ -0,0 +1,10 @@\n+a new text\n'
    })

    patches_2_ref = item_ref.collection('patches').document("2")
    patches_2_ref.set({
        "client_rev": 2,
        "create_date": firestore.SERVER_TIMESTAMP,
        "other_node_create_date": firestore.SERVER_TIMESTAMP,
        "patches": '@@ -1,10 +1,12 @@\n a new\n+er text\n'
    })

    # sys.exit(0)


    while True:
        # lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=server_patch_queue, args=())
        p_name = p.name
        # log.debug(p_name + " starting up")
        p.start()
        # Wait for x seconds or until process finishes
        p.join(300)
        if p.is_alive():
            log.debug(p_name + " timeouts")
            p.terminate()
            p.join()
        else:
            # log.debug(p_name + " finished ok")
            pass
