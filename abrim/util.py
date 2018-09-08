#!/usr/bin/env python

import sys
from functools import wraps
import logging
import zlib
import argparse
import json
import diff_match_patch
from flask import jsonify, request, Response


def resp(api_unique_code, msg, resp_json=None):
    log.debug("RESPONSE: {} :: {}".format(api_unique_code, msg))
    log.debug("-----------------------------------------------")
    if not resp_json:
        to_jsonify = {
            'api_unique_code': api_unique_code,
            'message': msg
        }
    else:
        to_jsonify = {
            'api_unique_code': api_unique_code,
            'message': msg,
            'content': resp_json
        }
    response = jsonify(to_jsonify)
    try:
        # get HTTP code:
        response.status_code = int(api_unique_code.split('/')[2])
    except IndexError:
        response.status_code = 500
    return response


def get_log(full_debug=False):
    if full_debug:
        # enable debug for HTTP requests
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
    else:
        # disable more with
        # for key in logging.Logger.manager.loggerDict:
        #    print(key)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

    # FIXME http://docs.python-guide.org/en/latest/writing/logging/
    # It is strongly advised that you do not add any handlers other
    # than NullHandler to your library's loggers.
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-7s %(asctime)s PID:%(process)-6s %(module)10s %(funcName)20s:%(lineno)-5s::: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')  # ,
    # disable_existing_loggers=False)
    logging.StreamHandler(sys.stdout)
    # log.debug(
    # "HTTP 405 - " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(
    #  sys._getframe().f_lineno))
    return logging.getLogger(__name__)


log = get_log(full_debug=False)


def create_diff_edits(text, shadow):
    if text == shadow:
        log.debug("both texts are the same...")
        return ""
    log.debug("about to diff \"{}\" with \"{}\"".format(shadow, text,))
    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = 1
    diff = diff_obj.diff_main(shadow, text)
    diff_obj.diff_cleanupSemantic(diff)  # FIXME: optional?
    patch = diff_obj.patch_make(diff)
    if patch:
        return diff_obj.patch_toText(patch)
    else:
        log.debug("no patch results...")
        return None


def fragile_patch_text(item_patches, text):
    log.debug("patching: {}\nwith: {}".format(item_patches, text))
    diff_obj = diff_match_patch.diff_match_patch()
    # these are FRAGILE patches and must match perfectly
    diff_match_patch.Match_Threshold = 0
    diff_match_patch.Match_Distance = 0
    patches =  diff_obj.patch_fromText(item_patches)
    patched_text, success = diff_obj.patch_apply(patches, text)
    return patched_text, success


def fuzzy_patch_text(item_patches, text):
    log.debug("patching: {}\nwith: {}".format(item_patches, text))
    diff_obj = diff_match_patch.diff_match_patch()
    # these are best-effort FUZZY patches
    diff_match_patch.Match_Threshold = 1
    diff_match_patch.Match_Distance = 10000
    patches =  diff_obj.patch_fromText(item_patches)
    patched_text, success = diff_obj.patch_apply(patches, text)
    return patched_text, success


def create_hash(text):
    adler32 = zlib.adler32(text.encode())
    log.debug("new hash {}".format(adler32))
    return adler32


def check_fields_in_dict(my_dict, fields):
    log.debug("checking {} for {}".format(my_dict,fields))
    is_ok = True
    for field in fields:
        try:
            _ = my_dict[field]
        except KeyError:
            log.error("missing '{}' in dict".format(field))
            is_ok = False
    return is_ok


# def check_request_method(request, method):
#     if request.method == method:
#         return True
#     return False


def check_crc(text, crc):
    log.debug("checking CRC of {} to {}".format(text, crc))
    text_crc = zlib.adler32(text.encode())

    try:
        int_crc = int(crc)
    except ValueError:
        log.error("request CRC isn't int: {} {}".format(crc, type(crc), ))
        return False

    if int_crc != text_crc:
        log.error("CRCs don't match {} {}".format(int_crc, text_crc, ))
        return False
    else:
        return True


def get_crc(text):
    # maybe save the CRC to avoid recalculating but it makes more complex updating the DB by hand...
    # is this premature optimization?
    return zlib.adler32(text.encode())


# responses


def response_parse(raw_response):
    log.debug("Response: {}".format(raw_response.text))
    response_http = raw_response.status_code
    response_dict = json.loads(raw_response.text)
    api_unique_code = response_dict['api_unique_code']
    log.debug("API response: {} HTTP response: {} Dict: {}".format(api_unique_code, response_http, response_dict))
    return api_unique_code, response_http, response_dict

# auth


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == 'secret'


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            log.warning("request not authenticated")
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# args

def _parse_args_helper():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id", help="Node ID")
    parser.add_argument("-p", "--port", help="Port")
    parser.add_argument("-l", "--logginglevel", help="Logging level")
    # parser.add_argument("-i", "--initdb", help="Init DB", action='store_true')
    args = parser.parse_args()
    if not args.port or int(args.port) <= 0:
        return None, None, None
    return args.id, args.port, args.logginglevel


def args_init():
    # import pdb; pdb.set_trace()
    args_id, args_port, args_logginglevel = _parse_args_helper()
    if not args_id:
        print("use -i to specify a node id")
        return None, None
    if not args_port or int(args_port) <= 0:
        print("use -p to specify a port")
        return None, None
    # before_request()
    return args_id, int(args_port)


if __name__ == "__main__":
    pass
