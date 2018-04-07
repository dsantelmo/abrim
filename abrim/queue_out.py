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
def send_queue(transaction, item_ref, item_id):
    # /nodes/node_1/items/item_1/queue_1_to_process/0/nodes/node_2
    known_nodes = ['node_2', 'node_3',]  # FIXME load config

    url_base = "http://localhost:5002"
    url_node = "node_1"  # FIXME don't trust node_id from url
    url_route = "users/user_1/nodes/{}/items/{}".format(url_node, item_id, )
    url = "{}/{}".format(url_base, url_route, )
    urls = {'node_2': url,}

    try:
        queue = item_ref.collection('queue_1_to_process').order_by('client_rev').limit(1).get()

        for queue_snapshot in queue:
            log.debug("checking id {}".format(queue_snapshot.id))
            rev_ref = item_ref.collection('queue_1_to_process').document(str(queue_snapshot.id))
            for node in known_nodes:
                try:
                    url = urls[node]
                except KeyError:
                    # log.debug("node {} without url".format(node))
                    continue

                queue_ref = rev_ref.collection('nodes').document(node)
                try:
                    queue_dict = queue_ref.get(transaction=transaction).to_dict()
                except google.api.core.exceptions.NotFound:
                    # this node doesn't match the node in the query
                    # FIXME this is an abomination... stop querying to fail...
                    continue

                log.debug("processing item {}".format(item_id))
                log.debug("trying to post to {}".format(url))
                log.debug("processing queue_1_to_process rev {} for node {}".format(rev_ref.id, node,))
                log.debug(queue_dict)

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


def process_out_queue():
    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    result = send_queue(transaction, item_ref, item_id)

    if result:
        #lock.acquire()
        log.info("one entry from queue 1 was correctly processed")
        #lock.release()
    else:
        log.info("Nothing done! waiting 15 additional seconds")
        time.sleep(15)


if __name__ == '__main__':
    while True:
        #lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=process_out_queue, args=())
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
