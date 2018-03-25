#!/usr/bin/env python

import multiprocessing
import time
from random import randint
import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import requests
import json
import logging

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

#
# #for key in logging.Logger.manager.loggerDict:
# #    print(key)
# def date_handler(obj):
#     return obj.isoformat() if hasattr(obj, 'isoformat') else obj
#
#
# def __requests_post(url, payload):
#     #prepare payload
#     temp_str = json.dumps(payload, default=date_handler)
#     temp_dict = json.loads(temp_str)
#     return requests.post(
#       url,
#       headers={'Content-Type': 'application/json'},
#       # json=json.dumps(payload, default=date_handler)
#       json=temp_dict
#       )


@firestore.transactional
def try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before, new_text, client_rev, other_node_create_date, create_date):
    try:
        try:
            new_item = new_item_ref.get().to_dict()
            try:
                old_text_now = new_item['text']
            except KeyError:
                log.error("error getting existing text!")
                return False
        except google.api.core.exceptions.NotFound:
            old_text_now = ""
        if old_text_now == old_text_before:
            transaction.set(new_item_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
                'client_rev': client_rev,
                'other_node_create_date': other_node_create_date,
                'patch_create_date': create_date,
                'text': new_text,
            })
            log.info("server text patched!")

            patches_deleted_ref = other_node_item_ref.collection('patches_deleted').document(str(patch_ref.id))
            # FIXME save the patch here
            transaction.set(patches_deleted_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
            })
            log.debug("patch archived")

            transaction.delete(patch_ref)
            log.debug("patch deleted")

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
    log.debug("starting server_patch_queue")
    node_id = "node_2"
    other_node_id = "node_1"

    db = firestore.Client()
    other_nodes_ref = db.collection('nodes').document(node_id).collection('other_nodes')
    for other_node in other_nodes_ref.get():
        log.debug("processing patch queue from node {}".format(other_node.id))
        items_ref = other_nodes_ref.document(str(other_node.id)).collection('items')
        for item in items_ref.get():
            log.debug("processing patches from item {}".format(item.id))
            other_node_item_ref = items_ref.document(str(item.id))
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
                    log.debug("node {} item {} exists".format(node_id, item.id))
                    new_item_dict = new_item_ref.get().to_dict()
                    try:
                        old_text_before = new_item_dict['text']
                    except KeyError:
                        old_text_before = ""
                except google.api.core.exceptions.NotFound:
                    log.debug("node {} item {} doesn't exist".format(node_id, item.id))
                    old_text_before = ""

                diff_obj = diff_match_patch.diff_match_patch()
                # these are FUZZY patches and mustn't match perfectly
                diff_match_patch.Match_Threshold = 1
                patches_obj = diff_obj.patch_fromText(patches)
                new_text, success = diff_obj.patch_apply(patches_obj, old_text_before)
                log.debug(new_text)
                log.debug(success)

                if not success:
                    log.debug("Patch failed. I should discard the patch") #FIXME
                    time.sleep(100)

                transaction = db.transaction()
                result = try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before, new_text, client_rev, other_node_create_date, create_date)
                if result:
                    log.info("one patch was correctly processed")
                else:
                    log.info("Not patched! waiting 2 additional seconds")
                    time.sleep(2)


if __name__ == '__main__':
    while True:
        #lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=server_patch_queue, args=())
        p_name = p.name
        #log.debug(p_name + " starting up")
        p.start()
        # Wait for x seconds or until process finishes
        p.join(300)
        if p.is_alive():
            log.debug(p_name + " timeouts")
            p.terminate()
            p.join()
        else:
            #log.debug(p_name + " finished ok")
            pass
