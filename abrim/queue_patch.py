#!/usr/bin/env python

import multiprocessing
import time
import zlib
import diff_match_patch
import google
import grpc
from google.cloud import firestore
from abrim.config import Config
from abrim.util import get_log, create_diff_edits
log = get_log(full_debug=False)


@firestore.transactional
def try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before, new_text, client_rev,
                       other_node_create_date, create_date, item_id):
    try:
        try:
            new_item = new_item_ref.get().to_dict()
            log.debug("try_to_apply_patch::new_item: {}".format(new_item))
            try:
                old_text_now = new_item['text']
                if not old_text_before:
                    raise KeyError
            except KeyError:
                log.debug("error getting existing text! I'm going to assume is a newly create item and continue...")
                old_text_now = ""
        except google.api.core.exceptions.NotFound:
            old_text_now = ""
        if old_text_now == old_text_before:
            patches_deleted_ref = other_node_item_ref.collection('patches_deleted').document(str(patch_ref.id))

            # create edits
            text_patches = create_diff_edits(new_text, old_text_before)
            old_shadow_adler32 = zlib.adler32(old_text_before.encode())
            shadow_adler32 = zlib.adler32(new_text.encode())
            log.debug("old_shadow_adler32 {}".format(old_shadow_adler32))
            log.debug("shadow_adler32 {}".format(shadow_adler32))
            # old_shadow_sha512 = hashlib.sha512(old_shadow.encode()).hexdigest()
            # shadow_sha512 = hashlib.sha512(new_text.encode()).hexdigest()
            # log.debug("old_shadow_sha512 {}".format(old_shadow_sha512))
            # log.debug("shadow_sha512 {}".format(shadow_sha512))

            # prepare the update of shadow and client text revision
            try:
                transaction.update(new_item_ref, {
                    'last_update_date': firestore.SERVER_TIMESTAMP,
                    'text': new_text,
                    'shadow': new_text,
                    'client_rev': client_rev,
                })
                # queue_ref = new_item_ref.collection('queue_1_to_process').document(str(client_rev))
                # transaction.set(queue_ref, {
                #     'create_date': firestore.SERVER_TIMESTAMP,
                #     'client_rev': client_rev,
                #     'action': 'edit_item',
                #     'text_patches': text_patches,
                #     'old_shadow_adler32': old_shadow_adler32,
                #     'shadow_adler32': shadow_adler32,
                # })
            except (grpc._channel._Rendezvous,
                    google.auth.exceptions.TransportError,
                    google.gax.errors.GaxError,
                    ):
                log.error("Connection error to Firestore")
                return False
            log.info("server text patched!")

            # FIXME save the patch here
            transaction.set(patches_deleted_ref, {
                'create_date': firestore.SERVER_TIMESTAMP,
            })
            log.debug("patch archived")
            transaction.delete(patch_ref)
            log.debug("original patch deleted")

            return True
        else:
            log.debug("server text changed. Discarding...")
            return False
    except (grpc._channel._Rendezvous,
            google.auth.exceptions.TransportError,
            google.gax.errors.GaxError,
            ):
        log.error("Connection error to Firestore")
        raise Exception


def server_patch_queue():
    # log.debug("starting server_patch_queue")
    node_id = "node_2"
    other_node_id = "node_1"

    db = firestore.Client()
    other_nodes_ref = db.collection('nodes').document(node_id).collection('other_nodes')
    for other_node in other_nodes_ref.get():
        # log.debug("processing patch queue from node {}".format(other_node.id))
        items_ref = other_nodes_ref.document(str(other_node.id)).collection('items')
        for item in items_ref.get():
            # log.debug("processing patches from item {}".format(item.id))
            other_node_item_ref = items_ref.document(item.id)
            patches_ref = other_node_item_ref.collection('patches')
            for patch in patches_ref.order_by('client_rev').get():
                log.debug("/nodes/{}/other_nodes/{}/items/{}/patches/{}".format(node_id,other_node.id,item.id,patch.id))
                patch_ref = patches_ref.document(str(patch.id))
                patch_dict = patch_ref.get().to_dict()
                log.debug(patch_dict)
                try:
                    patches = patch_dict['patches']
                    client_rev = patch_dict['client_rev']
                    other_node_create_date = patch_dict['other_node_create_date']
                    create_date = patch_dict['create_date']
                except KeyError:
                    log.error("KeyError in patch. Wait 5 seconds")
                    time.sleep(5)
                    return False

                # now we should get the server text and try to fuzzy apply the patch to it
                # if the patch fails discard the patch
                # if the patch works and server text has not changed, atomically accept the patch and change the text
                # if the server text has changed after the patch repeat the process
                new_items_ref = db.collection('nodes').document(node_id).collection('items')
                new_item_ref = new_items_ref.document(str(item.id))
                try:
                    new_item_dict = new_item_ref.get().to_dict()
                    log.debug("node {} item {} exists".format(node_id, item.id))
                    try:
                        old_text_before = new_item_dict['text']
                        if not old_text_before:
                            raise KeyError
                    except KeyError:
                        old_text_before = ""
                except google.api.core.exceptions.NotFound:
                    log.debug("node {} item {} doesn't exist".format(node_id, item.id))

                    config = Config("node_2")
                    create_item(config, str(item.id))
                    old_text_before = ""

                diff_obj = diff_match_patch.diff_match_patch()
                # these are FUZZY patches and mustn't match perfectly
                diff_match_patch.Match_Threshold = 1
                try:
                    log.debug("about to patch this: {}".format(patches))
                    patches_obj = diff_obj.patch_fromText(patches)
                except ValueError as ve:
                    log.error(ve)
                    return

                new_text, success = diff_obj.patch_apply(patches_obj, old_text_before)
                log.debug(new_text)
                log.debug(success)

                if not success:
                    log.debug("Patch failed. I should discard the patch")  # FIXME
                    time.sleep(100)

                transaction = db.transaction()
                result = try_to_apply_patch(transaction, new_item_ref, other_node_item_ref, patch_ref, old_text_before,
                                            new_text, client_rev, other_node_create_date, create_date, str(item.id))
                if result:
                    log.info("one patch was correctly processed")
                else:
                    log.info("Not patched! waiting 2 additional seconds")
                    time.sleep(2)


def _check_first_patch(config):
    return config.db.check_first_patch()


def _get_item(config, item_id):
    return config.db.get_item(item_id)


def process_out_patches(lock, node_id):
    config = Config(node_id="node_2")
    try:
        item, other_node, n_rev, m_rev, patches, old_crc, new_crc = _check_first_patch(config)
        _, text, item_crc = _get_item(config, item)

        if old_crc == item_crc:
            # original text from client is the same as current text from server, just apply the patch and finish
            log.debug("CRCs match, client text and server text are the same")
            raise Exception("implement me! 1")
        else:
            raise Exception("implement me! 2")
    except TypeError:
        # log.debug("no patches")
        pass


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
