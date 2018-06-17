#!/usr/bin/env python

import sys
from abrim.util import get_log, create_diff_edits, create_hash
from abrim.config import Config
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
        config.db.save_new_shadow(other_node_id, item_id, new_text, rev, other_node_rev)

        diffs = create_diff_edits(new_text, old_shadow)  # maybe doing a slow blocking diff in a transaction is wrong
        old_hash = create_hash(old_shadow)
        new_hash = create_hash(new_text)
        log.debug("old_hash: {}, new_hash: {}, diffs: {}".format(old_hash, new_hash, diffs))

        config.db.enqueue_client_edits(other_node_id, item_id, diffs, old_hash, new_hash, rev, other_node_rev)

    config.db.end_transaction()


if __name__ == "__main__":
    node_id = "node_1"
    # config = Config(node_id, drop_db=True)
    config_ = Config(node_id)
    config_.db.add_known_node('node_2', "http://localhost:5002")

    log.debug("NODE ID: {}".format(config_.node_id,))
    log.debug("db_path: {}".format(config_.db.db_path))

    # item_id = uuid.uuid4().hex
    item_id_ = "item_1"

    update_item(config_, item_id_, "")
    update_item(config_, item_id_, "a new text")
    update_item(config_, item_id_, "a newer text")
    sys.exit(0)
