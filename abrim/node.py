#!/usr/bin/env python

import sys
import diff_match_patch
from google.cloud import firestore
import grpc
import google
import logging
import os
import zlib
import hashlib
from pathlib import Path
import sqlite3

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
from util import get_log, create_diff_edits, create_hash, AbrimConfig
log = get_log(full_debug=False)


def update_item(config, item_id, new_text=""):
    config.db.start_transaction("update_item")

    config.db.save_item(item_id, new_text)

    for other_node_id, _ in config.db.get_known_nodes():
        rev, other_node_rev, old_shadow = config.db.get_rev_shadow(other_node_id, item_id)

        if old_shadow == new_text and rev > -1:
            log.info("new text equals old shadow, nothing done! for {} at {}".format(item_id, other_node_id,))
            continue

        rev += 1
        other_node_rev += 1
        text_patches = create_diff_edits(new_text, old_shadow)
        old_shadow_adler32 = create_hash(old_shadow)
        shadow_adler32 = create_hash(new_text)

        log.info("new enqueued edit for {} (rev {}) at {}".format(item_id, rev, other_node_id,))
        sys.exit(0)
        config.db.enqueue_client_edits(other_node_id, item_id, new_text, old_shadow, rev, other_node_rev)

    config.db.end_transaction()


if __name__ == "__main__":
    node_id = "node_1"
    # config = AbrimConfig(node_id, drop_db=True)
    config = AbrimConfig(node_id)
    config.db.add_known_node('node_2', "http://localhost:5002")

    log.debug("NODE ID: {}".format(config.node_id,))
    log.debug("db_path: {}".format(config.db.db_path))

    # item_id = uuid.uuid4().hex
    item_id = "item_1"

    update_item(config, item_id, "")
    update_item(config, item_id, "a new text")
    update_item(config, item_id, "a newer text")
    sys.exit(0)
