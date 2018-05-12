#!/usr/bin/env python

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))  # FIXME use pathlib
# noinspection PyPep8,PyUnresolvedReferences
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
        config.db.save_new_shadow(other_node_id, item_id, new_text, rev, other_node_rev)
        config.db.enqueue_client_edits(other_node_id, item_id, new_text, old_shadow, rev, other_node_rev)

    config.db.end_transaction()


if __name__ == "__main__":
    node_id = "node_1"
    # config = AbrimConfig(node_id, drop_db=True)
    config_ = AbrimConfig(node_id)
    config_.db.add_known_node('node_2', "http://localhost:5002")

    log.debug("NODE ID: {}".format(config_.node_id,))
    log.debug("db_path: {}".format(config_.db.db_path))

    # item_id = uuid.uuid4().hex
    item_id_ = "item_1"

    update_item(config_, item_id_, "")
    update_item(config_, item_id_, "a new text")
    update_item(config_, item_id_, "a newer text")
    sys.exit(0)
