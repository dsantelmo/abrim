import sys
import os
import unittest
import argparse
import mock
import flask
from werkzeug.exceptions import InternalServerError, NotFound
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

    #
    # init methods
    #
    def test_init_and_parse_without_argv(self):
        self.assertEqual((None, None, None), node._parse_args_helper())
        self.assertRaises(InternalServerError, node._init)

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

    #
    # flask route methods
    #
    def test_send_sync_get(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items', methods=[ 'GET'])
        with node.app.test_request_context('/users/1/nodes/1/items', method='GET') as test_req:
            node.app.preprocess_request()
            sys.argv.append('-i')
            sys.argv.append('-p')
            sys.argv.append(str(self.port_to_test))
            node._init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items')
            response = node._send_sync('1','1')
            self.assertEqual(response.headers.get('Content-Type'), 'application/json')
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'{\n  "items": [], \n  "status": "OK"\n}\n')
            self.assertEqual(response.mimetype, 'application/json')

    def test_send_sync_post(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items', methods=[ 'GET'])
        with node.app.test_request_context('/users/1/nodes/1/items', method='POST') as test_req:
            node.app.preprocess_request()
            sys.argv.append('-i')
            sys.argv.append('-p')
            sys.argv.append(str(self.port_to_test))
            node._init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items')
            self.assertRaises(NotFound, node._send_sync, '1', '1')

def _main():
    unittest.main()


if __name__ == '__main__':
    _main()