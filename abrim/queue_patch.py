#!/usr/bin/env python

import multiprocessing
import time
from abrim.config import Config
from abrim.util import get_log, patch_text
log = get_log(full_debug=False)


def _check_first_patch(config, other_node):
    return config.db.check_first_patch(other_node)


def _get_item(config, item_id):
    return config.db.get_item(item_id)


def _patch_server_text(config, item, other_node, n_rev, patches, text, old_crc, new_crc):
    patched_text, success = patch_text(patches, text)
    if not success:
        log.info("patching failed. just archive the patch")
        config.db.start_transaction()
        config.db.archive_patch(item, other_node, n_rev)
        config.db.delete_patch(item, other_node, n_rev)
        config.db.end_transaction()
        return False

    config.db.start_transaction()
    _, _, item_crc_again = _get_item(config, item)
    # if the server text has not changed, save the new text
    if old_crc == item_crc_again:
        config.db.save_item(item, patched_text, new_crc)
        config.db.archive_patch(item, other_node, n_rev)
        config.db.delete_patch(item, other_node, n_rev)
        config.db.end_transaction()
        log.info("patching ended ok")
    else:
        log.debug("server text changed meanwhile, cancelling this patch")
        config.db.rollback_transaction()
    return True


def process_out_patches(lock, node_id):
    config = Config(node_id)

    there_was_nodes = False
    # to avoid one node hoarding the queue, process one patch a time for each node
    for other_node_id in config.db.get_nodes_from_patches():
        there_was_nodes = True
        log.debug(other_node_id)
        try:
            item, other_node, n_rev, m_rev, patches, old_crc, new_crc = _check_first_patch(config, other_node_id)
            if item:
                _, text, item_crc = _get_item(config, item)

                if old_crc == item_crc:
                    # original text from client is the same as current text from server, just apply the patch and finish
                    log.debug("CRCs match, client text and server text are the same")
                    _patch_server_text(config, item, other_node, n_rev, patches, text, old_crc, new_crc)
                else:
                    log.debug("CRCs don't match, different texts")
                    time.sleep(15)
                    raise Exception("implement me! 2")
            else:
                log.debug("no items for this node")
                time.sleep(15)
                raise Exception("implement me! 3")
        except TypeError:
            # log.debug("no patches")
            pass
    if there_was_nodes:
        log.debug("processed some patches")
    else:
        # log.debug("no processing done, sleeping for a bit")
        time.sleep(2)


if __name__ == '__main__':
    log.info("queue_patch started")
    node_id_ = "node_2"
    while True:
        lock = multiprocessing.Lock()
        p = multiprocessing.Process(target=process_out_patches, args=(lock, node_id_, ))
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
