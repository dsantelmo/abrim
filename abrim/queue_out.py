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

# enable debug for HTTP requests
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1

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


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


def __requests_post(url, payload):
    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      json=json.dumps(payload, default=date_handler)
      )

### def items_send_get(node_id, item_id=None):
###     url_for_get = ""
###     if item_id:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items/" + item_id  # FIXME SANITIZE THIS
###     else:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items"  # FIXME SANITIZE THIS
###     return requests.get(
###       url_for_get,
###       headers={'Content-Type': 'application/json'}
###       )


def user_3_process_queue(lock):
    #
    # end UI client part, start the queue part
    #

    # read the queues

    node_id = "node_1"
    item_id = "item_1"

    db = firestore.Client()
    node_ref = db.collection('nodes').document(node_id)
    item_ref = node_ref.collection('items').document(item_id)

    transaction = db.transaction()

    @firestore.transactional
    def send_queue1(transaction, item_ref):
        try:
            queue = item_ref.collection('queue_1_to_process').order_by('client_rev').limit(1).get()

            for queue_snapshot in queue:
                queue_1_ref = item_ref.collection('queue_1_to_process').document(str(queue_snapshot.id))
                lock.acquire()
                log.debug("processing item {} queue_1_to_process item {}".format(item_id, queue_1_ref.id, ))
                lock.release()

                # NOW SENT THE QUEUE ITEM TO THE SERVER
                queue_1_dict = queue_1_ref.get().to_dict()
                url_base = "http://localhost:5001"
                url_route = "users/user_1/nodes/{}/items/{}".format(node_id,item_id,)
                url = "{}/{}".format(url_base,url_route,)
                log.debug(url)
                try:
                    log.debug("about to POST this: {}".format(queue_1_dict,))
                    post_result = __requests_post(url, queue_1_dict)

                    log.info("HTTP Status code is: {}".format(post_result.status_code,))
                    post_result.raise_for_status()  # fail if not 2xx

                    queue_2_ref = item_ref.collection('queue_2_sent').document(str(queue_1_ref.id))
                    transaction.set(queue_2_ref, {
                        'create_date': firestore.SERVER_TIMESTAMP,
                        'client_rev': queue_1_ref.id,
                        'action': 'processed_item',
                    })

                    transaction.delete(queue_1_ref)
                except requests.exceptions.ConnectionError:
                    log.info("ConnectionError!! Sleep 10 secs")
                    time.sleep(10)
                except requests.exceptions.HTTPError as err:
                    log.error(err)
                    time.sleep(10)
                # log.debug("{}".format(queue_1_dict),)
                # try:
                #     item_action = queue_1_dict['action']
                #     item_client_rev = queue_1_dict['client_rev']
                #     item_create_date = queue_1_dict['create_date']
                #     text_patches = None
                #     try:
                #         text_patches = queue_1_dict['text_patches']
                #     except AttributeError:
                #         pass
                # except AttributeError:
                #     raise

                break
            else:
                lock.acquire()
                log.info("queue query got no results")
                lock.release()
                return False
        except (grpc._channel._Rendezvous,
                google.auth.exceptions.TransportError,
                google.gax.errors.GaxError,
                ):
            lock.acquire()
            log.error("Connection error to Firestore")
            lock.release()
            raise Exception
        lock.acquire()
        log.info("queue 1 sent!")
        lock.release()
        return True

    result = send_queue1(transaction, item_ref)

    lock.acquire()
    if result:
        log.info("one entry from queue 1 was correctly processed")
    else:
        log.info("no entries in queue 1. Nothing done! waiting 5 seconds")
        time.sleep(5)
    lock.release()


if __name__ == '__main__':
    while True:
        lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=user_3_process_queue, args=(lock,))
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
