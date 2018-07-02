#!/usr/bin/env python

import sys
import time
from abrim.util import get_log, create_diff_edits, create_hash
from abrim.config import Config
log = get_log(full_debug=False)


def update_local_item(config, item_id, new_text=""):
    config.db.start_transaction("update_local_item")

    config.db.save_item(item_id, new_text)

    for other_node_id, _ in config.db.get_known_nodes():
        n_rev, m_rev, old_shadow = config.db.get_latest_rev_shadow(other_node_id, item_id)
        n_rev += 1
        config.db.save_new_shadow(other_node_id, item_id, new_text, n_rev, m_rev)

        diffs = create_diff_edits(new_text, old_shadow)  # maybe doing a slow blocking diff in a transaction is wrong
        if n_rev == 0 or diffs:
            old_hash = create_hash(old_shadow)
            new_hash = create_hash(new_text)
            log.debug("old_hash: {}, new_hash: {}, diffs: {}".format(old_hash, new_hash, diffs))
            config.db.enqueue_client_edits(other_node_id, item_id, diffs, old_hash, new_hash, n_rev, m_rev)
        else:
            log.warn("no diffs. Nothing done!")

    config.db.end_transaction()


if __name__ == "__main__":
    config = Config("node_1", drop_db=True)
    # config = Config("node_1")
    config.db.add_known_node('node_2', "http://localhost:5002")

    config.db.sql_debug_trace(True)

    log.debug("NODE ID: {}".format(config.node_id,))
    log.debug("db_path: {}".format(config.db.db_path))

    # item_id = uuid.uuid4().hex
    item_id_ = "item_1"

    update_local_item(config, item_id_, "")
    time.sleep(2)
    update_local_item(config, item_id_, "a new text")
    time.sleep(2)
    update_local_item(config, item_id_, "a newer text")
    sys.exit(0)
