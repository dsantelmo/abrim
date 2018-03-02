from unittest import TestCase
import logging
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # FIXME use pathlib

from abrim import node

class TestNode(TestCase):
    config = None

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.config = node.AbrimConfig(
            node_id="test_node1",
            db_prefix="test_db_"
        )

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_config(self):
        self.assertEqual(self.config.node_id, "test_node1")

    def test_create_diff_edits(self):
        self.assertEqual(
            node.create_diff_edits('aaaaaa', 'aaabaa'),
            '@@ -1,6 +1,6 @@\n aaa\n-b\n+a\n aa\n'
        )

    def test_user_0_create(self):
        item_id = "item_1"
        self.assertTrue(node.user_0_create(self.config, item_id))

