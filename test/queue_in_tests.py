from unittest import TestCase
import logging
import warnings
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # FIXME use pathlib

from abrim import node, queue_in

class TestNode(TestCase):
    config = None

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.config = node.AbrimConfig(
            node_id="test_node1",
            db_prefix="test_db_")
        self.config.item_user_id = "user_1"
        self.config.node_id = "test_node2"
        self.config.item_id = "item_1"
        self.config.queue_in = None
        self.config.item_create_date = "2018 - 01 - 29T21: 35:15.785000 + 00: 00"
        self.config.item_action = "create_item"
        self.config.item_node_id = "node_1"
        self.config.item_rev = 0

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_config(self):
        self.assertEqual(self.config.node_id, "test_node2")


    def test_create_item(self):
        item_id = "item_1"
        new_text = "original text"
        warnings.simplefilter("ignore") # suppress "ResourceWarning: unclosed <ssl.SSLSocket..." warning
        self.assertTrue(queue_in.server_create_item(self.config))
