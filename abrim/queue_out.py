#!/usr/bin/env python

import multiprocessing
import traceback
import time
import requests
import json
from abrim.util import get_log, resp
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
        api_unique_code = response_dict['api_unique_code']
        log.debug("API response: {} HTTP response: {} Dict: {}".format(api_unique_code, response_http, response_dict))
        return response_http, api_unique_code
    except requests.exceptions.ConnectionError:
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
    # config.db.sql_debug_trace(True)

    # lock.acquire()
    # log.debug("NODE ID: {}".format(config.node_id,))
    # lock.release()

    result = None
    there_was_nodes = False
    for other_node_id, other_node_url in config.db.get_known_nodes():
        there_was_nodes = True
        if other_node_url:
            queue_limit = config.edit_queue_limit
            while queue_limit > 0:
                config.db.start_transaction()

                edit, item, m_rev, n_rev, rowid = get_first_queued_edit(config, other_node_id)
                if not rowid:
                    break

                url = prepare_url(config, item, other_node_url)
                try:
                    response_http, api_unique_code = send_sync(edit, url)

                    response_http = int(response_http)

                    if response_http == 201:
                        if (
                                api_unique_code == "queue_in/get_sync/201/done" or
                                api_unique_code == "queue_in/get_sync/201/ack"):
                            log.debug("POST successful, archiving this item to queue_2_sent")
                            config.db.archive_edit(rowid)
                            config.db.delete_edit(rowid)
                            config.db.end_transaction()
                            if api_unique_code == "queue_in/get_sync/201/ack":
                                log.info("EVENT: remote node seems overloaded") #  TODO: save events
                            log.debug("-----------------------------------------------------------------")
                        else:
                            raise Exception("implement me! 8")
                    elif response_http == 404:
                        if api_unique_code == "queue_in/get_sync/404/not_shadow":
                            log.info("queue_in/get_sync/404/not_shadow")
                            got_shadow, shadow = config.db.get_shadow(item,
                                                                      other_node_id,
                                                                      m_rev,
                                                                      n_rev)
                            config.db.rollback_transaction()
                            shadow_json = {'n_rev': n_rev,
                                           'm_rev': m_rev,
                                           'shadow': ""}
                            if got_shadow:
                                shadow_json['shadow'] = shadow

                            log.debug("trying to send the shadow again")
                            shad_http, shad_api_unique_code = send_sync(shadow_json, url + "/shadow", use_put=True)
                            if shad_http == 201 and shad_api_unique_code == "queue_in/get_shadow/201/ack":
                                log.info("EVENT: remote needed the shadow") #  TODO: save events
                            else:
                                raise Exception("implement me! 2")
                        else:
                            raise Exception("implement me! 3")
                    elif response_http == 403:
                        if api_unique_code == "queue_in/get_sync/403/no_match_revs":
                            log.debug("queue_in/get_sync/403/no_match_revs")
                            config.db.rollback_transaction()
                            raise Exception("implement me! 4")
                        elif api_unique_code == "queue_in/get_sync/403/check_crc_old":
                            raise Exception("implement me! 5")
                        else:
                            raise Exception("implement me! 6")
                    else:
                        # raise for the rest of the codes
                        log.error("Undefined HTTP response: {} {}".format(response_http, api_unique_code))
                        config.db.rollback_transaction()
                        raise Exception("Undefined HTTP response")  # fail for the rest of HTTP codes
                except (requests.exceptions.ConnectionError) as err:
                    config.db.rollback_transaction()
                    log.debug("ConnectionError: sleep 15 secs")
                    time.sleep(15)
                except (requests.exceptions.HTTPError, KeyError, json.decoder.JSONDecodeError) as err:
                    config.db.rollback_transaction()
                    log.debug(err)
                    traceback.print_exc()
                    log.debug("sleep 15 secs")
                    time.sleep(15)
                except Exception as err:
                    config.db.rollback_transaction()
                    log.error(err)
                    traceback.print_exc()
                    log.debug("sleep 15 secs")
                    time.sleep(15)
                finally:
                    queue_limit -= 1

    if there_was_nodes:
        config.db.end_transaction(True)
    if result:
        lock.acquire()
        log.info("one entry from queue 1 was correctly processed")
        lock.release()
    else:
        lock.acquire()
        # log.info("Nothing done! waiting 1 additional second")
        lock.release()
        time.sleep(1)


def get_first_queued_edit(config, other_node_id):
    rowid, edit = config.db.get_first_queued_edit(other_node_id)
    if not edit or not rowid:
        return None, None, None, None, None
    else:
        item = edit["item"]
        n_rev = edit["n_rev"]
        m_rev = edit["m_rev"]
        return edit, item, m_rev, n_rev, rowid


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
