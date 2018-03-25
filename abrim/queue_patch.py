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
def try_to_apply_patch(transaction, new_item_ref):
    # try:
    #     queue = item_ref.collection('queue_1_to_process').order_by('client_rev').limit(1).get()
    #
    #     for queue_snapshot in queue:
    #         queue_1_ref = item_ref.collection('queue_1_to_process').document(str(queue_snapshot.id))
    #         log.debug("processing queue_1_to_process item {}".format(queue_1_ref.id, ))
    #
    #         # NOW SENT THE QUEUE ITEM TO THE SERVER
    #         queue_1_dict = queue_1_ref.get().to_dict()
    #         try:
    #             log.debug("about to POST this: {}".format(queue_1_dict,))
    #             post_result = __requests_post(url, queue_1_dict)
    #
    #             log.info("HTTP Status code is: {}".format(post_result.status_code,))
    #             post_result.raise_for_status()  # fail if not 2xx
    #
    #             log.debug("POST successful, archiving this item to queue_2_sent")
    #             queue_2_ref = item_ref.collection('queue_2_sent').document(str(queue_1_ref.id))
    #             transaction.set(queue_2_ref, {
    #                 'create_date': firestore.SERVER_TIMESTAMP,
    #                 'client_rev': queue_1_ref.id,
    #                 'action': 'processed_item',
    #             })
    #
    #             log.debug("archiving successful, deleting item from queue_1_to_process")
    #             transaction.delete(queue_1_ref)
    #         except requests.exceptions.ConnectionError:
    #             log.info("ConnectionError!! Sleep 15 secs")
    #             time.sleep(15)
    #             return False
    #         except requests.exceptions.HTTPError as err:
    #             log.error(err)
    #             log.info("Sleep 15 secs")
    #             time.sleep(15)
    #             return False
    #         break
    #     else:
    #         log.info("queue query got no results")
    #         return False
    # except (grpc._channel._Rendezvous,
    #         google.auth.exceptions.TransportError,
    #         google.gax.errors.GaxError,
    #         ):
    #     log.error("Connection error to Firestore")
    #     raise Exception
    # log.info("queue 1 sent!")
    return True


def server_patch_queue():
    node_id = "node_2"
    other_node_id = "node_1"

    db = firestore.Client()
    other_nodes_ref = db.collection('nodes').document(node_id).collection('other_nodes')
    for other_node in other_nodes_ref.get():
        log.debug("processing patch queue from node {}".format(other_node.id))
        items_ref = other_nodes_ref.document(str(other_node.id)).collection('items')
        for item in items_ref.get():
            log.debug("processing patches from item {}".format(item.id))
            patches_ref = items_ref.document(str(item.id)).collection('patches')
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
                    new_item = new_item_ref.get()
                    sys.exit(0) # FIXME
                    time.sleep(99999)
                except google.api.core.exceptions.NotFound:
                    log.debug("node {} item {} doesn't exist".format(node_id, item.id))
                    text = ""

                diff_obj = diff_match_patch.diff_match_patch()
                # these are FUZZY patches and mustn't match perfectly
                diff_match_patch.Match_Threshold = 1
                patches_obj = diff_obj.patch_fromText(patches)
                new_item_text, success = diff_obj.patch_apply(patches_obj, text)
                log.debug(new_item_text)
                log.debug(success)

                if not success:
                    log.debug("Patch failed. I should discard the patch") #FIXME
                    time.sleep(100)

                transaction = db.transaction()
                try_to_apply_patch (transaction, new_item_ref)


    #transaction = db.transaction()

    # log.debug("processing item {}".format(item_id))
    # url_base = "http://localhost:5001"
    # # url_base = "https://requestb.in/xctmjexc"
    # # url_base = "http://mockbin.org/bin/424a595a-a802-48ba-a44a-b6ddb553a0ee"
    # url_route = "users/user_1/nodes/{}/items/{}".format(node_id, item_id, )
    # url = "{}/{}".format(url_base, url_route, )
    # log.debug(url)
    #
    # result = patch_queue(transaction, item_ref, url)
    #
    # if result:
    #     #lock.acquire()
    #     log.info("one entry from queue 1 was correctly processed")
    #     #lock.release()
    # else:
    #     log.info("Nothing done! waiting 2 additional seconds")
    #     time.sleep(2)


if __name__ == '__main__':
    while True:
        #lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=server_patch_queue, args=())
        p_name = p.name
        log.debug(p_name + " starting up")
        p.start()
        # Wait for x seconds or until process finishes
        p.join(30)
        if p.is_alive():
            log.debug(p_name + " timeouts")
            p.terminate()
            p.join()
        else:
            log.debug(p_name + " finished ok")
