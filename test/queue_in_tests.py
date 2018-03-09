from unittest import TestCase
import logging
import warnings
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # FIXME use pathlib

from abrim import node, queue_in


# to test:
#
# import requests
#
# url = "http://127.0.0.1:5001/users/user_1/nodes/node_1/items/item_1"
#
# payload = "{\n\t\"action\": \"create_item\",\n\t\"create_date\": \"2018-01-29T21:35:15.785000+00:00\",\n\t\"client_rev\": 0\n}"
#
# headers = {
#     'Content-Type': "application/json",
#     'Cache-Control': "no-cache",
#     'Postman-Token': "173c0991-7697-8506-bbdb-f433d4909c20"
#     }
#
#
# response = requests.request("POST", url, data=payload, headers=headers)
# print(response.status_code)
#
# or:
# import http.client
#
# conn = http.client.HTTPConnection("127.0.0.1:5001")
#
# payload = "{\n\t\"action\": \"create_item\",\n\t\"create_date\": \"2018-01-29T21:35:15.785000+00:00\",\n\t\"client_rev\": 0\n}"
#
# headers = {
#     'Content-Type': "application/json",
#     'Cache-Control': "no-cache",
#     'Postman-Token': "0cf06ca7-5611-8aed-3739-14bde335ef00"
#     }
#
#
# conn.request("POST", "users/user_1/nodes/node_1/items/item_1", payload, headers)
#
# res = conn.getresponse()
# #data = res.read()
# #print(data.decode("utf-8"))
# print(res.code)


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
