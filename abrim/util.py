#!/usr/bin/env python

import sys
import diff_match_patch
import logging
import zlib
from flask import jsonify


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
                        format='%(levelname)-5s %(asctime)s PID:%(process)-6s %(module)10s %(funcName)20s:%(lineno)-5s::: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')  # ,
    # disable_existing_loggers=False)
    logging.StreamHandler(sys.stdout)
    return logging.getLogger(__name__)


log = get_log(full_debug=False)


def create_diff_edits(text, shadow):
    if text == shadow:
        log.debug("both texts are the same...")
        return None
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


def resp(http_code, api_code, api_code_unique, message):
    response = jsonify({
        'http_code': http_code,
        'api_code': api_code,
        'api_code_unique': api_code_unique,
        'message': message
    })
    log.debug("HTTP {} - {} - {} - {}".format(http_code, api_code, api_code_unique, message))
    response.status_code = http_code
    return response


if __name__ == "__main__":
    pass
