#!/usr/bin/env python

import multiprocessing
import time
from random import randint
import sys
from google.cloud import firestore
import grpc
import google
import requests
import json
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from node import get_log, get_item_ref, get_queue_1_revs_ref, AbrimConfig
log = get_log(full_debug=False)

#for key in logging.Logger.manager.loggerDict:
#    print(key)
def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


def __requests_post(url, payload):
    #prepare payload
    temp_str = json.dumps(payload, default=date_handler)
    temp_dict = json.loads(temp_str)
    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      # json=json.dumps(payload, default=date_handler)
      json=temp_dict
      )


@firestore.transactional
def send_queue(transaction, item_ref, config, remote_node_id):
    # /nodes/node_1/items/item_1/queue_1_to_process/0/nodes/node_2
    node_id = config.node_id
    item_id = config.item_id
    url_base = "http://localhost:5002"
    url_route = "users/user_1/nodes/{}/items/{}".format(node_id, item_id, ) # FIXME don't trust node_id from url
    url = "{}/{}".format(url_base, url_route, )
    urls = {'node_2': url,}

    try:
        # log.debug("checking queue for node: {}".format(remote_node_id))
        queue = get_queue_1_revs_ref(item_ref, remote_node_id).order_by('shadow_client_rev').limit(1).get()

        for queue_snapshot in queue:
            # log.debug("checking id {}".format(queue_snapshot.id))
            rev_ref = get_queue_1_revs_ref(item_ref, remote_node_id).document(str(queue_snapshot.id))
            try:
                url = urls[remote_node_id]
            except KeyError:
                # log.debug("node {} without url".format(node))
                continue

            try:
                queue_dict = rev_ref.get(transaction=transaction).to_dict()
            except google.api.core.exceptions.NotFound:
                log.error("queue item not found")
                log.info("Sleep 15 secs")
                time.sleep(15)
                return False

            log.debug("processing item {}".format(item_id))
            log.debug("trying to post to {}".format(url))
            log.debug("processing queue_1_to_process rev {} for node {}".format(rev_ref.id, remote_node_id, ))

            # NOW SENT THE QUEUE ITEM TO THE SERVER
            try:
                log.debug("about to POST this: {}".format(queue_dict,))
                post_result = __requests_post(url, queue_dict)

                log.info("HTTP Status code is: {}".format(post_result.status_code,))
                post_result.raise_for_status()  # fail if not 2xx

                log.debug("POST successful, archiving this item to queue_2_sent")
                queue_2_ref = item_ref.collection('queue_2_sent').document(str(queue_ref.id))
                transaction.set(queue_2_ref, {
                    'create_date': firestore.SERVER_TIMESTAMP,
                    'client_rev': queue_ref.id,
                    'action': 'processed_item',
                })

                log.debug("archiving successful, deleting item from queue_1_to_process")
                transaction.delete(queue_ref)
            except requests.exceptions.ConnectionError:
                log.info("ConnectionError!! Sleep 15 secs")
                time.sleep(15)
                return False
            except requests.exceptions.HTTPError as err:
                log.error(err)
                log.info("Sleep 15 secs")
                time.sleep(15)
                return False
            break
        else:
            # log.info("queue query got no results")
            return False
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        raise Exception
    log.info("queue 1 sent!")
    return True


def process_out_queue(config, node_id):
    db = firestore.Client()
    item_ref = get_item_ref(db, config, config.item_id)
    transaction = db.transaction()
    result = send_queue(transaction, item_ref, config, node_id)

    if result:
        #lock.acquire()
        log.info("one entry from queue 1 was correctly processed")
        #lock.release()
    else:
        log.info("Nothing done! waiting 15 additional seconds")
        time.sleep(15)


if __name__ == '__main__':
    config = AbrimConfig("node_1")
    config.known_nodes_ids = ['node_2', 'node_3', ]
    config.item_id = "item_1"

    while True:
        for node_id in config.known_nodes_ids:
            #lock = multiprocessing.Lock()
            p = multiprocessing.Process(target=process_out_queue, args=(config, node_id))
            p_name = p.name
            # log.debug(p_name + " starting up")
            p.start()
            # Wait for x seconds or until process finishes
            p.join(30)
            if p.is_alive():
                log.debug(p_name + " timeouts")
                p.terminate()
                p.join()
            else:
                # log.debug(p_name + " finished ok")
                pass
