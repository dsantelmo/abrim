import sys
import os
import unittest
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import Item


class ClassesTestCase(unittest.TestCase):

    port_to_test = None

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        pass

    def test_class_item_constructor(self):
        item = Item()
        self.assertTrue(isinstance(item.id, uuid.UUID))

    def test_class_item_constructor_from_existing_id(self):
        item = Item.from_existing_id(uuid.uuid4())
        self.assertTrue(isinstance(item.id, uuid.UUID))


def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()
