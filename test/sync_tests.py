import sys
import os
import unittest
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import sync


class SyncTestCase(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_step_1_create_diff(self):
        self.assertEqual([(0, 'text '), (-1, 'shadow'), (1, 'text')],
                         sync.step_1_create_diff("text text", "text shadow", 0.1))

    def test_step_2_create_edits(self):
        self.assertEqual("(0, 'text ')(-1, 'shadow')(1, 'text')",
                         sync.step_2_create_edits([(0, 'text '), (-1, 'shadow'), (1, 'text')]))


def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()