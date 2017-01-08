import sys
import os
import re
import unittest
import logging
import flask
import werkzeug.exceptions
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim import node


class NodeTestCase(unittest.TestCase):

    port_to_test = None

    def setUp(self):
        logging.disable(logging.CRITICAL)
        sys.argv = [__name__]
        self.port_to_test = 5001

        file_format = node.app.config['DB_FILENAME_FORMAT']
        if "_test" not in file_format:
            node.app.config['DB_FILENAME_FORMAT'] += "_test"

    def tearDown(self):
        if 'DB_PATH' in node.app.config:
            try:
                os.unlink(node.app.config['DB_PATH'])
            except OSError:
                pass
        else:  # pragma: no cover
            raise Exception
        logging.disable(logging.NOTSET)

    def _standard_init(self):
        sys.argv.append('-i')
        sys.argv.append('-p')
        sys.argv.append(str(self.port_to_test))
        node._init()
        node.app.preprocess_request()
    #
    # init methods
    #

    def test_init_and_parse_without_argv(self):
        self.assertEqual((None, None, None), node._parse_args_helper())
        self.assertRaises(werkzeug.exceptions.InternalServerError, node._init)

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
        with node.app.test_request_context('/users/1/nodes/1/items', method='GET'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items')
            response = node._send_sync('1','1')
            response_data = re.sub('[\s+]', '', response.data.decode("utf-8") )
            self.assertEqual(response.headers.get('Content-Type'), 'application/json')
            self.assertEqual(response.status, "200 OK")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response_data, '{"items":[],"status":"OK"}')
            self.assertEqual(response.mimetype, 'application/json')

    def test_send_sync_post(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items', methods=[ 'GET'])
        with node.app.test_request_context('/users/1/nodes/1/items', method='POST'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items')
            self.assertRaises(werkzeug.exceptions.NotFound, node._send_sync, '1', '1')

    def test_get_sync_patch_empty(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1', method='PATCH'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.NotFound, node._get_sync, '1', '1', '1')

    def test_get_sync_post_empty(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1', method='POST'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.UnsupportedMediaType, node._get_sync, '1', '1', '1')

    def test_get_sync_post_wrong_payload(self):
        jsonified_data = '{"this_should_fail": "with_HTTP_422_UnprocessableEntity"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='POST',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.UnprocessableEntity, node._get_sync, '1', '1', '1')

    def test_get_sync_post_with_payload_then_get(self):
        jsonified_data = '{"content": "content_text"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='POST',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertEqual(('', 201), node._get_sync('1', '1', '1'))
            with node.app.test_request_context('/users/1/nodes/1/items/1', method='GET'):
                self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
                response = node._get_sync('1', '1', '1')
                response_data = re.sub('[\s+]', '', response.data.decode("utf-8") )
                self.assertEqual(response.headers.get('Content-Type'), 'application/json')
                self.assertEqual(response.status, "200 OK")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_data, u'{"item":{"content":"content_text","item_id":"1","shadow":{"client_ver":0,"server_ver":0,"shadow":"content_text","shadow_id":1}},"status":"OK"}')
                self.assertEqual(response.mimetype, 'application/json')

    def test_get_sync_post_double_post(self):
        jsonified_data = '{"content": "content_text"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='POST',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertEqual(('', 201), node._get_sync('1', '1', '1'))
            with node.app.test_request_context('/users/1/nodes/1/items/1',
                                               method='POST',
                                               content_type='application/json',
                                               data=jsonified_data):
                self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
                self.assertRaises(werkzeug.exceptions.Conflict, node._get_sync, '1', '1', '1')

    def test_get_sync_put_empty(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1', method='PUT'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.UnsupportedMediaType, node._get_sync, '1', '1', '1')

    def test_get_sync_put_wrong_payload(self):
        jsonified_data = '{"this_should_fail": "with_HTTP_422_UnprocessableEntity"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='PUT',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.UnprocessableEntity, node._get_sync, '1', '1', '1')

    def test_get_sync_put_with_payload_then_get(self):
        jsonified_data = '{"content": "content_text"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='PUT',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertEqual(('', 201), node._get_sync('1', '1', '1'))
            with node.app.test_request_context('/users/1/nodes/1/items/1', method='GET'):
                self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
                response = node._get_sync('1', '1', '1')
                response_data = re.sub('[\s+]', '', response.data.decode("utf-8") )
                self.assertEqual(response.headers.get('Content-Type'), 'application/json')
                self.assertEqual(response.status, "200 OK")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_data, '{"item":{"content":"content_text","item_id":"1","shadow":null},"status":"OK"}')
                self.assertEqual(response.mimetype, 'application/json')

    def test_get_sync_put_double_put(self):
        jsonified_data = '{"content": "content_text"}'
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1',
                                           method='PUT',
                                           content_type='application/json',
                                           data=jsonified_data):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertEqual(('', 201), node._get_sync('1', '1', '1'))
            with node.app.test_request_context('/users/1/nodes/1/items/1',
                                               method='PUT',
                                               content_type='application/json',
                                               data=jsonified_data):
                self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
                self.assertEqual(('', 204), node._get_sync('1', '1', '1'))

    def test_get_sync_get(self):
        # @app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>',
        # methods=['GET', 'POST', 'PUT'])
        with node.app.test_request_context('/users/1/nodes/1/items/1', method='GET'):
            self._standard_init()
            self.assertEqual(flask.request.path, '/users/1/nodes/1/items/1')
            self.assertRaises(werkzeug.exceptions.NotFound, node._get_sync, '1', '1', '1')


def _main():
    unittest.main()


if __name__ == '__main__':  # pragma: no cover
    _main()
