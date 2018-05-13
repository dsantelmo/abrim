#!/usr/bin/env python

import multiprocessing
import time
import sys
import requests
import json
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from node import get_log, AbrimConfig
log = get_log(full_debug=False)

# for key in logging.Logger.manager.loggerDict:
#     print(key)
def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


def __requests_post(url, payload):
    log.debug("about to POST: {}".format(payload))
    log.debug("to URL: {}".format(url))
    #prepare payload
    temp_str = json.dumps(payload, default=date_handler)
    temp_dict = json.loads(temp_str)
    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      # json=json.dumps(payload, default=date_handler)
      json=temp_dict
      )


def send_edit(edit, other_node_url):
    #log.debug("/nodes/{}/items/{}/queue_1_to_process/{}/revs/{}".format(config.node_id, config.item_id, remote_node_id, rev_ref.id, ))
    # NOW SENT THE QUEUE ITEM TO THE SERVER
    try:
        post_result = __requests_post(other_node_url, edit)
        log.info("HTTP Status code is: {}".format(post_result.status_code,))
        post_result.raise_for_status()  # fail if not 2xx
        log.debug("POST successful, archiving this item to queue_2_sent")
    except requests.exceptions.ConnectionError:
        log.info("ConnectionError!! Sleep 15 secs")
        raise
    except requests.exceptions.HTTPError as err:
        log.error(err)
        log.info("Sleep 15 secs")
        raise


def get_first_queued_edit(config, other_node_id):
    return config.db.get_first_queued_edit(other_node_id)


def archive_edit(config, edit_rowid):
    return config.db.archive_edit(edit_rowid)


def delete_edit(config, edit_rowid):
    return config.db.delete_edit(edit_rowid)


def prepare_url(config_, item_id, other_node_url):
    url_route = "{}/users/user_1/nodes/{}/items/{}".format(
        other_node_url,
        config_.node_id,
        item_id, )  # FIXME don't trust node_id from url
    return url_route


def process_out_queue(lock, node_id):
    config = AbrimConfig(node_id)

    lock.acquire()
    log.debug("NODE ID: {}".format(config.node_id,))
    log.debug("db_path: {}".format(config.db.db_path))
    lock.release()

    result = None
    for other_node_id, other_node_url in config.db.get_known_nodes():
        if other_node_url:
            queue_limit = config.edit_queue_limit
            while queue_limit > 0:
                config.db.start_transaction("process_out_queue")
                edit_rowid, edit = get_first_queued_edit(config, other_node_id)
                if not edit or not edit_rowid:
                    break
                url = prepare_url(config, edit["item"], other_node_url)
                try:
                    send_edit(edit, url)
                    archive_edit(config, edit_rowid)
                    delete_edit(config, edit_rowid)
                    config.db.end_transaction()
                except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as err:
                    log.debug(err)
                    time.sleep(15)
                finally:
                    queue_limit -= 1
    if result:
        lock.acquire()
        log.info("one entry from queue 1 was correctly processed")
        lock.release()
    else:
        lock.acquire()
        log.info("Nothing done! waiting 15 additional seconds")
        lock.release()
        time.sleep(15)


if __name__ == '__main__':
    node_id_ = "node_1"
    while True:
        lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=process_out_queue, args=(lock, node_id_, ))
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
