import logging
import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class DbTestCase(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

#    def test_get_or_create_shadow(self):
#        self.assertEqual(1,
#                         _get_or_create_shadow(user_id, node_id, item_id, client_text))
#
#    results = db.get_shadow(user_id, node_id, item_id)
#    if results is None:
#        shadow_id = db.create_shadow(user_id, node_id, item_id, client_text)

def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()
