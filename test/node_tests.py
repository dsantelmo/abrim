import sys
import os
import unittest
import argparse
import mock
from werkzeug.exceptions import InternalServerError
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import node


class NodeTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init_empty(self):
        sys.argv = [__name__]
        self.assertRaises(InternalServerError, node._init)

    def test_init_with_argv_with_i(self):
        sys.argv.append('-i')
        sys.argv.append('-p')
        sys.argv.append('5001')
        self.assertEqual(node._init(), 5001)

    def test_init_with_argv_without_i(self):
        sys.argv.append('-p')
        sys.argv.append('5001')
        #self.assertEqual(node._init(), 5001)

    def test_init_with_argv_without_port(self):
        sys.argv = [__name__]
        sys.argv.append('-p')  # note that only "-p" and not the port number is added
        with self.assertRaises(SystemExit) as argv_ex:
            node._init()
        self.assertEqual(argv_ex.exception.code, 2)


def _main():
    unittest.main()


if __name__ == '__main__':
    _main()