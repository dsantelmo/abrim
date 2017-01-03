import sys
import os
import unittest
import argparse
import mock
from werkzeug.exceptions import InternalServerError
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import node


class NodeTestCase(unittest.TestCase):

    port_to_test = None

    def setUp(self):
        sys.argv = [__name__]
        self.port_to_test = 5001

        file_format = node.app.config['DB_FILENAME_FORMAT']
        if not "_test" in file_format:
            node.app.config['DB_FILENAME_FORMAT'] = node.app.config['DB_FILENAME_FORMAT'] + "_test"

    def tearDown(self):
        if 'DB_PATH' in node.app.config:
            try:
                os.unlink(node.app.config['DB_PATH'])
            except OSError as error:
                pass

    def test_init_and_parse_without_argv(self):
        self.assertEqual((None, None, None), node._parse_args_helper())
        self.assertRaises(InternalServerError, node._init)  # FIXME: is this a bug? no ()

    def test_init_and_parse_with_argv_without_i(self):
        sys.argv.append('-p')
        sys.argv.append(str(self.port_to_test))
        self.assertEqual((str(self.port_to_test), None, False), node._parse_args_helper())
        self.assertEqual(self.port_to_test, node._init())

    def test_init_and_parse_with_argv_without_port(self):
        sys.argv = [__name__]
        sys.argv.append('-p')  # note that only "-p" and not the port number is added
        with self.assertRaises(SystemExit) as argv_ex:
            node._parse_args_helper()
        self.assertEqual(argv_ex.exception.code, 2)
        with self.assertRaises(SystemExit) as argv_ex:
            node._init()
        self.assertEqual(argv_ex.exception.code, 2)

    def test_parse_args_helper_with_argv(self):
        sys.argv.append('-i')
        sys.argv.append('-p')
        sys.argv.append(str(self.port_to_test))
        sys.argv.append('-l')
        sys.argv.append('info')


    def test_init_and_parse_with_argv(self):
        sys.argv.append('-i')
        sys.argv.append('-p')
        sys.argv.append(str(self.port_to_test))
        sys.argv.append('-l')
        sys.argv.append('info')

        self.assertEqual((str(self.port_to_test), 'info', True), node._parse_args_helper())

        self.assertEqual(node._init(), self.port_to_test)
        self.assertEqual(node.app.config['API_URL'], "http://127.0.0.1:" + str( int(self.port_to_test)+1 ))
        self.assertEqual(node.app.config['NODE_PORT'], self.port_to_test)
        self.assertEqual(node.app.config['USER_ID'], "the_user")
        self.assertEqual(node.app.config['NODE_ID'], "node" + str(self.port_to_test))

def _main():
    unittest.main()


if __name__ == '__main__':
    _main()