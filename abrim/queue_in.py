#!/usr/bin/env python

import argparse
import logging
import sys

from flask import Flask, request, abort, jsonify, Response

LOGGING_LEVELS = {'critical': logging.CRITICAL,
                  'error': logging.ERROR,
                  'warning': logging.WARNING,
                  'info': logging.INFO,
                  'debug': logging.DEBUG}
# FIXME http://docs.python-guide.org/en/latest/writing/logging/
# It is strongly advised that you do not add any handlers other
# than NullHandler to your library's loggers.
logging.basicConfig(level=logging.DEBUG,
              format='%(asctime)s __ %(module)-12s __ %(levelname)-8s: %(message)s',
              datefmt='%Y-%m-%d %H:%M:%S')  # ,
              # disable_existing_loggers=False)
logging.StreamHandler(sys.stdout)
log = logging.getLogger(__name__)

app = Flask(__name__)

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

@app.errorhandler(405)
def errorhandler405(e):
    return Response('405', 405, {'Allow':'POST'})

@app.route('/users/<string:user_id>/nodes/<string:node_id>/items/<string:item_id>', methods=['POST'])
def _get_sync(user_id, node_id, item_id):
    if request.method == 'POST':
        req_json = request.get_json()
        log.debug("{} {} {} {}".format(user_id, node_id, item_id, req_json,))

        try:
            item_action = req_json['action']
            item_rev = req_json['client_rev']
            item_create_date = req_json['create_date']
            log.debug("action: {}, rev: {}, date: {}".format(item_action,item_rev, item_create_date,))
            try:
                item_patches = req_json['text_patches']
                log.debug("patches: {}".format(item_patches,))
            except KeyError:
                log.debug("no patches")
            # return '', 201  # HTTP 201: Created
            abort(501)
        except KeyError:
            log.error("HTTP 400 Bad Request")
            abort(400)  # 400 Bad Request
        log.error("HTTP 500 Internal Server Error")
        abort(500)  # 500 Internal Server Error
    else:
        log.debug("HTTP 405 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(405)  # 405 Method Not Allowed



def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    #parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None
    return args.port, args.logginglevel #, args.initdb



def _init():
    #import pdb; pdb.set_trace()
    log.info("Hajime!")
    args_port, args_logginglevel = _parse_args_helper()
    if args_port and int(args_port) > 0:
        client_port = int(args_port)
        app.config['API_URL'] = "http://127.0.0.1:" + str( int(args_port)+1 )
        app.config['NODE_PORT'] = client_port
        # FIXME client side config
        app.config['USER_ID'] = "the_user"
        app.config['NODE_ID'] = "node" + args_port
    else:
        print("use -p to specify a port")
        abort(500)
    if args_logginglevel:
        logging_level = LOGGING_LEVELS.get(args_logginglevel, logging.NOTSET)
        log.setLevel(logging_level)
    log.debug("DEBUG logging enabled")
    # before_request()
    return client_port


def __end():
    # db.close_db()
    pass


@app.before_request
def before_request():
    # db.prepare_db_path(app.config['DB_PATH'])
    pass


@app.teardown_request
def teardown_request(exception):
    __end()


if __name__ == "__main__":  # pragma: no cover
    client_port = _init()
    #app.run(host='0.0.0.0', port=client_port, use_reloader=False)
    app.run(host='0.0.0.0', port=client_port)
    __end()
