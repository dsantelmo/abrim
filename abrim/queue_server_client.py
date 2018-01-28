#!/usr/bin/env python

import argparse
import logging
import os
import sys

from flask import Flask, request, abort, jsonify

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

@app.route('/users/<string:user_id>/nodes/<string:node_id>/items', methods=[ 'GET'])
def _send_sync(user_id, node_id):
    if request.method == 'GET':
        return items_receive_get(user_id, node_id)
    else:
        log.debug("HTTP 404 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
        abort(404)



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
