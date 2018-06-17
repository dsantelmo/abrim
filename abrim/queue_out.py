#!/usr/bin/env python

import multiprocessing
import time
import requests
import json
from abrim.util import get_log, err_codes
from abrim.config import Config
log = get_log(full_debug=False)


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
        post_response = __requests_post(other_node_url, edit)
        response_http = post_response.status_code
        response_dict = json.loads(post_response.text)
        api_code = response_dict['api_code']
        if response_http == 201 and api_code == err_codes['SYNC_OK']:
            log.debug("POST successful, archiving this item to queue_2_sent")
            raise("implement me!")
        elif response_http == 404 and api_code == err_codes['NO_SHADOW']:
            log.debug(err_codes['NO_SHADOW'])
            raise("implement me!")
        elif response_http == 404 and api_code == err_codes['CHECK_REVS']:
            log.debug(err_codes['CHECK_REVS'])
            raise("implement me!")
        else:
            # raise for the rest of the codes
            post_response.raise_for_status()  # fail if not 2xx
            raise("Undefined HTTP response")  # fail for the rest of HTTP codes
    except requests.exceptions.ConnectionError:
        log.info("ConnectionError!! Sleep 15 secs")
        raise
    except requests.exceptions.HTTPError as err:
        post_response = err.response.status_code
        log.info("HTTPError!! code: {} Sleep 15 secs".format(post_response))
        raise
    except AttributeError:
        log.error("AttributeError in the response payload. Sleep 15 secs")
        raise


def prepare_url(config_, item_id, other_node_url):
    url_route = "{}/users/user_1/nodes/{}/items/{}".format(
        other_node_url,
        config_.node_id,
        item_id, )  # FIXME don't trust node_id from url
    return url_route


def process_out_queue(lock, node_id):
    config = Config(node_id)

    lock.acquire()
    log.debug("NODE ID: {}".format(config.node_id,))
    lock.release()

    result = None
    for other_node_id, other_node_url in config.db.get_known_nodes():
        if other_node_url:
            queue_limit = config.edit_queue_limit
            while queue_limit > 0:
                config.db.start_transaction("process_out_queue")
                edit_rowid, edit = config.db.get_first_queued_edit(other_node_id)
                if not edit or not edit_rowid:
                    break
                url = prepare_url(config, edit["item"], other_node_url)
                try:
                    send_edit(edit, url)

                    config.db.archive_edit(edit_rowid)
                    config.db.delete_edit(edit_rowid)

                    config.db.end_transaction()
                except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as err:
                    config.db.rollback_transaction()
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
    log.info("queue_out started")
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
