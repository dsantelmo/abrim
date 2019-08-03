#!/usr/bin/env python

import multiprocessing
import time
from abrim.config import Config
from abrim.util import get_log, args_init, fuzzy_patch_text, get_crc, create_diff_edits, create_hash

log = get_log('critical')


def _check_first_patch(config, other_node):
    return config.db.check_first_patch(other_node)


def _get_item(config, item_id):
    return config.db.get_item(item_id)


def _patch_server_text(config, item, other_node, n_rev, patches, text, item_crc):
    patched_text, success = fuzzy_patch_text(patches, text)
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
    if item_crc == item_crc_again:
        # config.db.save_item(item, patched_text)
        _update_item(config, item, patched_text)
        config.db.archive_patch(item, other_node, n_rev)
        config.db.delete_patch(item, other_node, n_rev)
        config.db.end_transaction()
        log.info("patching ended ok")
    else:
        log.debug("server text changed meanwhile, cancelling this patch")
        config.db.rollback_transaction()
    return True


def _check_item_exists(config, item_id):
    return config.db.get_item(item_id)


def _enqueue_edit(config, other_node_id, item_id, diffs,  n_rev, m_rev, old_shadow):
    hash_ = create_hash(old_shadow)
    temp_diffs = diffs.replace('\n', ' ')
    log.debug(f"enquing edits ({n_rev},{m_rev}) old_hash: {hash_}, diffs: {temp_diffs}")
    config.db.enqueue_client_edits(other_node_id, item_id, diffs, hash_, n_rev, m_rev, old_shadow)


def _update_item(config, item_id, new_text):
    log.debug(f"saving item {item_id} with {new_text}")
    new_text_crc = get_crc(new_text)
    config.db.update_item(item_id, new_text, new_text_crc)
    for known_node in config.db.get_known_nodes():
        other_node_id = known_node["id"]

        n_rev, m_rev, old_shadow = config.db.get_latest_rev_shadow(other_node_id, item_id)

        log.debug(f"latest revs for that item in {other_node_id} are {n_rev} - {m_rev}")
        log.debug(f"creating diffs")
        diffs = create_diff_edits(new_text, old_shadow)  # maybe doing a slow blocking diff in a transaction is wrong
        if diffs:
            _enqueue_edit(config, other_node_id, item_id, diffs, n_rev, m_rev, old_shadow)

            # now save the new shadow for the other node
            n_rev += 1
            log.debug(f"saving new shadow for {other_node_id} with crc {new_text_crc}")
            config.db.save_new_shadow(other_node_id, item_id, new_text, n_rev, m_rev, new_text_crc)
        else:
            log.warning("no diffs. Nothing done!")


def _new_item(config, item_id, new_text):
    log.debug(f"saving NEW item {item_id} with {new_text}")
    new_text_crc = get_crc(new_text)
    config.db.save_new_item(item_id, new_text, new_text_crc)  # save the new item
    known_nodes = config.db.get_known_nodes()
    log.debug(f"known_nodes: {known_nodes}")
    for known_node in known_nodes:
        other_node_id = known_node["id"]

        n_rev = 0
        m_rev = 0
        old_shadow = ""

        # create and enqueue the edit for the new item
        log.debug(f"creating diffs")
        diffs = create_diff_edits(new_text, old_shadow)  # TODO: maybe doing a slow blocking diff in a transaction is wrong
        if diffs:
            _enqueue_edit(config, other_node_id, item_id, diffs, n_rev, m_rev, old_shadow)

            # now save the new shadow for the other node
            n_rev += 1
            log.debug(f"saving new shadow for {other_node_id} with crc {new_text_crc}")
            config.db.save_new_shadow(other_node_id, item_id, new_text, n_rev, m_rev, new_text_crc)
        else:
            log.warning("no diffs. Nothing done!")


def process_out_patches(lock, node_id, port):
    config = Config(node_id, port)
    # config.db.sql_debug_trace(True)

    there_was_posts = False
    try:
        rowid, item_id, new_text, _, _ = config.db.get_post_pending()
        if rowid:
            config.db.start_transaction("posts queue")
            there_was_posts = True
            rowid, item_id, new_text, _, _ = config.db.get_post_pending()
            item_exists, item, _ = _check_item_exists(config, item_id)

            if item_exists:
                _update_item(config, item_id, new_text)
            else:
                _new_item(config, item_id, new_text)
            config.db.update_post_pending(rowid)

    except Exception as err:
        config.db.rollback_transaction()
        log.error(err)
    else:
        if there_was_posts:
            config.db.end_transaction()

    there_was_nodes = False
    # to avoid one node hoarding the queue, process one patch a time for each node
    for other_node_id in config.db.get_nodes_from_patches():
        there_was_nodes = True
        log.debug(other_node_id)
        try:
            # config.db.sql_debug_trace(True)
            patch_found_item, other_node, n_rev, m_rev, patches, crc = _check_first_patch(config, other_node_id)
            if not patch_found_item:
                log.debug("no patch found for this item for this node")
                time.sleep(2)
                raise Exception("implement me! 3")

            config.db.start_transaction()
            item_found, text, item_crc = _get_item(config, patch_found_item)
            if not item_found:
                if n_rev == 0 and m_rev == 0:  # if revs == 0 is a new so we can create an empty one
                    log.debug(f"creating new empty item for patch {patch_found_item}")
                    text = ""
                    item_crc = 1
                    config.db.save_new_item(patch_found_item, text, item_crc)
                else:
                    log.debug("no patch found for this item for this node")
                    time.sleep(2)
                    raise Exception("implement me! 4")
            config.db.end_transaction()

            if crc == item_crc:
                # original text from client is the same as current text from server, just apply the patch and finish
                log.debug("CRCs match, client text and server text are the same")
            else:
                log.debug(f"CRCs don't match, different texts: {crc} - {item_crc}")

            sucessful_patch = _patch_server_text(config, patch_found_item, other_node, n_rev, patches, text, item_crc)

            if sucessful_patch:
                log.debug("patch ok")
            else:
                log.error("patch failed")

        except TypeError:
            # log.debug("no patches")
            pass
    if there_was_nodes or there_was_posts:
        log.debug("processed some patches or posts")
    else:
        # log.debug("no processing done, sleeping for a bit")
        time.sleep(0.5)  # TODO: make this adaptative


if __name__ == '__main__':
    log.info("{} started".format(__file__))
    node_id_, client_port = args_init()
    if not node_id_ or not client_port:
        pass
    else:
        while True:
            lock = multiprocessing.Lock()
            p = multiprocessing.Process(target=process_out_patches, args=(lock, node_id_, client_port))
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
            time.sleep(1)  # TODO: make this adaptative
