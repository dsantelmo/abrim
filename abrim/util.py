#!/usr/bin/env python

import sys
import diff_match_patch
import logging
import zlib
from flask import jsonify


def resp(api_unique_code, msg, resp_json=None):
    log.debug("RESPONSE: {} :: {}".format(api_unique_code, msg))
    log.debug("-----------------------------------------------")
    if resp_json:
        to_jsonify = {
            'api_unique_code': api_unique_code,
            'message': msg
        }
    else:
        to_jsonify = {
            'api_unique_code': api_unique_code,
            'message': msg,
            'resp_json': resp_json
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


def patch_text(item_patches, text):
    log.debug("patching: {}\nwith: {}".format(item_patches, text))
    diff_obj = diff_match_patch.diff_match_patch()
    # these are FRAGILE patches and must match perfectly
    diff_match_patch.Match_Threshold = 0
    diff_match_patch.Match_Distance = 0
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


def check_request_method(request, method):
    if request.method == method:
        return True
    return False


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
    # TODO: think in maybe save the CRC to avoid recalculating but it makes more complex updating the DB by hand...


if __name__ == "__main__":
    pass
