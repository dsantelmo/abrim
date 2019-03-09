#!/usr/bin/env python

import multiprocessing
import traceback
import time
import requests
import json
from abrim.util import get_log, args_init, response_parse, post_request, put_request, ROUTE_FOR
from abrim.config import Config
log = get_log(full_debug=False)


def send_sync(edit, other_node_url, use_put=False):
    try:
        if use_put:
            p_response = put_request(other_node_url, edit)
        else:
            p_response = post_request(other_node_url, edit)

        api_unique_code, response_http, _ = response_parse(p_response)
        if api_unique_code and response_http:
            return response_http, api_unique_code
        else:
            raise Exception
    except requests.exceptions.ConnectionError:
        log.debug("send_sync ConnectionError")
        raise
    except requests.exceptions.HTTPError as err:
        post_response = err.response.status_code
        log.info(f"HTTPError!! code: {post_response} Sleep 15 secs")
        raise
    except json.decoder.JSONDecodeError as err:
        log.info(f"JSONDecodeError!! code: {err} Sleep 15 secs")
        raise
    except (AttributeError, TypeError):
        log.error("Error in the response payload. Sleep 15 secs")
        raise


def prepare_sync_url(config_, item_id, other_node_url, shadow=False):
    sync_or_shadow = 'sync'
    if shadow:
        sync_or_shadow = 'shadow'
    url_route = f"{other_node_url}{ROUTE_FOR['items']}/{item_id}/{sync_or_shadow}/{config_.node_id}"  # FIXME don't trust node_id from url
    return url_route


def prepare_shadow_url(config_, item_id, other_node_url):
    return prepare_sync_url(config_, item_id, other_node_url, shadow=True)


def process_out_queue(lock, node_id, port):
    config = Config(node_id, port)
    # config.db.sql_debug_trace(True)

    # lock.acquire()
    # log.debug("NODE ID: {}".format(config.node_id,))
    # lock.release()

    result = None
    for known_node in config.db.get_known_nodes():
        other_node_id = known_node["id"]
        other_node_url = known_node["base_url"]
        if other_node_url:
            queue_limit = config.edit_queue_limit
            while queue_limit > 0:
                config.db.start_transaction()
                # config.db.sql_debug_trace(True)
                edit, item, m_rev, n_rev, old_shadow, rowid = get_first_queued_edit(config, other_node_id)
                try:
                    edit.pop("old_shadow", None) # do not send old shadow during sync
                except AttributeError:
                    pass
                if not rowid:
                    # log.debug(f"not rowid for {other_node_id}")
                    break

                log.debug(f"other_node_url: {other_node_url}")
                sync_url = prepare_sync_url(config, item, other_node_url)
                try:
                    log.debug(f"about to send {edit} to {sync_url}")
                    response_http, api_unique_code = send_sync(edit, sync_url)

                    try:
                        response_http = int(response_http)
                    except TypeError:
                        response_http = 0

                    if response_http == 201:
                        if (
                                api_unique_code == "queue_in/post_sync/201/done" or
                                api_unique_code == "queue_in/post_sync/201/ack" or
                                api_unique_code == "queue_in/post_sync/201/lost_return_packet"):
                            log.debug("POST successful, archiving this item to queue_2_sent")
                            config.db.archive_edit(rowid)
                            config.db.delete_edit(rowid)
                            config.db.end_transaction()
                            if api_unique_code == "queue_in/post_sync/201/ack":
                                log.info("EVENT: remote node seems overloaded") #  TODO: save events
                            log.debug("-----------------------------------------------------------------")
                        else:
                            raise Exception("implement me! 8")
                    elif response_http == 404:  # the other node doesn't find a shadow, send it
                        if api_unique_code == "queue_in/post_sync/404/not_shadow":
                            log.info("queue_in/post_sync/404/not_shadow")
                            config.db.rollback_transaction()
                            shadow_json = {'n_rev': n_rev,
                                           'm_rev': m_rev,
                                           'shadow': old_shadow}

                            log.debug("trying to send the shadow again")
                            shadow_url = prepare_shadow_url(config, item, other_node_url)
                            shad_http, shad_api_unique_code = send_sync(shadow_json, shadow_url, use_put=True)
                            if shad_http == 201 and shad_api_unique_code == "queue_in/put_shadow/201/ack":
                                log.info("EVENT: remote needed the shadow") #  TODO: save events
                            elif shad_http == 201 and shad_api_unique_code == "queue_in/put_shadow/201/lost_return_packet":
                                log.info("EVENT: it seems that previously we have lost a return packet from that remote node")
                            else:
                                raise Exception("implement me! 2")
                        else:
                            config.db.rollback_transaction()
                            raise Exception("implement me! 3")
                    elif response_http == 403:
                        if api_unique_code == "queue_in/post_sync/403/no_match_revs":
                            log.debug("queue_in/post_sync/403/no_match_revs")
                            config.db.rollback_transaction()
                            raise Exception("implement me! 4")
                        elif api_unique_code == "queue_in/post_sync/403/check_crc":
                            raise Exception("implement me! 5")
                        else:
                            raise Exception("implement me! 6")
                    else:
                        # raise for the rest of the codes
                        log.error(f"Undefined HTTP response: {response_http} {api_unique_code}")
                        config.db.rollback_transaction()
                        raise Exception("Undefined HTTP response")  # fail for the rest of HTTP codes
                except requests.exceptions.ConnectionError:
                    log.debug("other node seems offline... sleep 5 secs")
                    config.db.rollback_transaction()
                    time.sleep(5) # TODO make this adaptative and break the for loop for the nodes whose wait time is not finished yet
                except (requests.exceptions.HTTPError,
                        requests.exceptions.ReadTimeout,
                        json.decoder.JSONDecodeError,
                        KeyError,
                        Exception, ) as err:
                    config.db.rollback_transaction()
                    log.debug(err)
                    traceback.print_exc()
                    log.debug("Exception... sleep 15 secs")
                    time.sleep(15)
                finally:
                    queue_limit -= 1
            config.db.end_transaction(True)

    if config.db.check_transaction():
        config.db.end_transaction(True)
    if result:
        lock.acquire()
        log.info("one entry from queue 1 was correctly processed")
        lock.release()
    else:
        lock.acquire()
        #log.info("Nothing done! waiting 0.5 additional seconds")
        lock.release()
        time.sleep(0.5)  # TODO: make this adaptative


def get_first_queued_edit(config, other_node_id):
    rowid, edit = config.db.get_first_queued_edit(other_node_id)
    if not edit or not rowid:
        return None, None, None, None, None, None
    else:
        item = edit["item"]
        n_rev = edit["n_rev"]
        m_rev = edit["m_rev"]
        old_shadow = edit["old_shadow"]
        log.debug(f"queued edits for {other_node_id}")
        return edit, item, m_rev, n_rev, old_shadow, rowid


if __name__ == '__main__':
    log.info(f"{__file__} started")
    node_id_, client_port = args_init()
    if not node_id_ or not client_port:
        pass
    else:
        while True:
            lock = multiprocessing.Lock()
            p = multiprocessing.Process(target=process_out_queue, args=(lock, node_id_, client_port ))
            p_name = p.name
            # log.debug(p_name + " starting up")
            p.start()
            # Wait for x seconds or until process finishes
            p.join(30)
            if p.is_alive():
                log.debug(f"{p_name} timeouts")
                p.terminate()
                p.join()
            else:
                # log.debug(p_name + " finished ok")
                pass
            time.sleep(3)  # TODO: make this adaptative
