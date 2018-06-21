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


def __prepare_request(url, payload):
    log.debug("about to POST/PUT: {}".format(payload))
    log.debug("to URL: {}".format(url))
    temp_str = json.dumps(payload, default=date_handler)
    json_dict = json.loads(temp_str)
    headers = {'Content-Type': 'application/json'}
    return headers, json_dict


def __requests_post(url, payload):
    headers, json_dict = __prepare_request(url, payload)
    return requests.post(url, headers = headers, json = json_dict)


def __requests_put(url, payload):
    headers, json_dict = __prepare_request(url, payload)
    return requests.put(url, headers = headers, json = json_dict)


def send_sync(edit, other_node_url, use_put=False):
    try:
        if use_put:
            p_response = __requests_put(other_node_url, edit)
        else:
            p_response = __requests_post(other_node_url, edit)
        log.debug("Response: {}".format(p_response.text))
        response_http = p_response.status_code
        response_dict = json.loads(p_response.text)
        api_code = response_dict['api_code']
        log.debug("API response: {} HTTP response: {} Dict: {}".format(api_code, response_http, response_dict))
        return response_http, api_code
    except requests.exceptions.ConnectionError:
        log.info("ConnectionError!! Sleep 15 secs")
        raise
    except requests.exceptions.HTTPError as err:
        post_response = err.response.status_code
        log.info("HTTPError!! code: {} Sleep 15 secs".format(post_response))
        raise
    except json.decoder.JSONDecodeError as err:
        log.info("JSONDecodeError!! code: {} Sleep 15 secs".format(err))
        raise
    except (AttributeError, TypeError):
        log.error("Error in the response payload. Sleep 15 secs")
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
                    response_http, api_code = send_sync(edit, url)

                    if response_http == 201 and api_code == err_codes['SYNC_OK']:
                        log.debug("POST successful, archiving this item to queue_2_sent")
                        config.db.archive_edit(edit_rowid)
                        config.db.delete_edit(edit_rowid)
                        config.db.end_transaction()
                    elif response_http == 404 and api_code == err_codes['NO_SHADOW']:
                        log.info(err_codes['NO_SHADOW'])
                        got_shadow, shadow = config.db.get_shadow(edit["item"],
                                                      other_node_id,
                                                      edit["other_node_rev"],
                                                      edit["rev"])
                        config.db.rollback_transaction()

                        shadow_json = {'rev': edit["rev"],
                                       'other_node_rev': edit["other_node_rev"],
                                       'shadow': ""}

                        if got_shadow:
                            shadow_json['shadow'] = shadow
                            send_sync(shadow_json, url + "/shadow", use_put=True)
                        else:
                            send_sync(shadow_json, url + "/shadow", use_put=True)
                    elif response_http == 404 and api_code == err_codes['CHECK_REVS']:
                        log.debug(err_codes['CHECK_REVS'])
                        config.db.rollback_transaction()
                        raise Exception("implement me!")
                    else:
                        # raise for the rest of the codes
                        config.db.rollback_transaction()
                        raise ("Undefined HTTP response")  # fail for the rest of HTTP codes
                except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError, KeyError, json.decoder.JSONDecodeError) as err:
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
