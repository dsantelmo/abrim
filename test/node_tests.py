from unittest import TestCase
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
