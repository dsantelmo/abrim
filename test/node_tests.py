from unittest import TestCase
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # FIXME use pathlib

from abrim import node

class TestNode(TestCase):
    config = None

    def setUp(self):
        self.config = node.AbrimConfig("test_node1")
        pass


    def tearDown(self):
        pass


    def test_config(self):
        self.assertEqual(self.config.node_id, "test_node1")

    def test_user_0_create(self):
        print(self.config.node_id)
        #self.fail()
