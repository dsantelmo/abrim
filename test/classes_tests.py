import sys
import os
import unittest
import logging
import uuid
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import DatastoreProvider, ItemDatastore, Item


class DatastoreProviderTestCase(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        pass

    def test_class_DatastoreProvider_constructor(self):
        datastore_provider = DatastoreProvider()
        self.assertTrue(isinstance(datastore_provider, DatastoreProvider))

    def test_class_DatastoreProvider_constructor_from_path(self):
        datastore_provider = DatastoreProvider.from_path("path")
        self.assertTrue(isinstance(datastore_provider, DatastoreProvider))

    def test_class_DatastoreProvider_constructor_from_ram(self):
        datastore_provider = DatastoreProvider.from_ram()
        self.assertTrue(isinstance(datastore_provider, DatastoreProvider))


class ItemDatastoreTestCase(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        pass

    def test_class_ItemDatastore_constructor(self):
        item_datastore = ItemDatastore()
        self.assertTrue(isinstance(item_datastore, ItemDatastore))


class ItemTestCase(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        pass

    def test_class_Item_constructor(self):
        item = Item()
        self.assertTrue(isinstance(item, Item))
        self.assertTrue(isinstance(item.id, uuid.UUID))

    def test_class_Item_constructor_from_existing_id(self):
        item = Item.from_existing_id(uuid.uuid4())
        self.assertTrue(isinstance(item, Item))
        self.assertTrue(isinstance(item.id, uuid.UUID))


def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()
