#!/usr/bin/env python

from contextlib import closing
import os
import sys
import tempfile #FIXME delete
import hashlib
import json
import argparse
import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
from flask import Flask, g, request, redirect, url_for, abort
import flask
import diff_match_patch
import requests
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.db import db



DIFF_TIMEOUT=0.1

# set FLASK_APP=client.py
# set FLASK_DEBUG=1
# python -m flask run
app = Flask(__name__)
app.debug = True
app.config['DB_FILENAME_FORMAT'] = 'abrimsync-{}.sqlite'
app.config['DB_SCHEMA_PATH'] = 'db\\schema.sql'


def connect_db():
    return db.connect_db(app.config['DB_PATH'])


def get_db():
    return db.get_db(g, app.config['DB_PATH'])


def init_db():
    db.init_db(app, g, app.config['DB_PATH'], app.config['DB_SCHEMA_PATH'])



#@app.route('/', methods=['POST',])
@app.route('/', methods=['GET', 'POST'])
def __root():
    abort(404)


@app.route('/datastore')
def __datastore():
    if request.method != 'GET':
        abort(404)
    else:
        return show_datastore_form()


@app.route('/send_sync', methods=['POST'])
def _send_sync():
    if request.method != 'POST':
        abort(404)
    else:
        return receive_sync(request)


@app.route('/send_shadow', methods=['POST'])
def _send_shadow():
    if request.method != 'POST':
        abort(404)
    else:
        return receive_shadow(request)


@app.route('/get_text', methods=['POST'])
def _get_text():
    if request.method != 'POST':
        abort(404)
    else:
        return get_text(request)


SERVER_ID='server1'

temp_server_file_name = os.path.join( tempfile.gettempdir(),
  tempfile.gettempprefix() + SERVER_ID)





def show_datastore_form():
    with closing(shelve.open(temp_server_file_name)) as d:
        temp_string = "<h1>Datastore</h1><h3>" + temp_server_file_name + "</h3>"
        return __print_iter_contents(d, 6, temp_string)

def __print_iter_contents(iter_d, depth, temp_string):
    if depth > 0:
        for k, element in iter_d.items():
            if isinstance(element, dict):
                temp_string = temp_string + "<li><b>{0} :</b></li>".format(k)
                temp_string = temp_string + "<ul>"
                temp_string = __print_iter_contents(element, depth - 1, temp_string)
                temp_string = temp_string + "</ul>"
            else:
                temp_string = temp_string + "<li><b>{0}</b> : {1}</li>".format(k, element)
    return temp_string


def receive_sync(request):
    #import pdb; pdb.set_trace()
    print("send_sync")
    req = request.json
    res = err_response('UnknownError', 'Non controlled error in server')
    if req and 'client_id' in req and 'client_shadow_cksum' in req and 'client_patches' in req:

        # FIXME: create atomicity
        #
        # steps 4 (atomic with 5, 6 & 7)
        #
        # The edits are applied to Server Text on a best-effort basis
        # Server Text is updated with the result of the patch. Steps 4 and 5
        # must be atomic, but they do not have to be blocking; they may be
        # repeated until Server Text stays still long enough.
        #
        # Client Text and Server Shadow (or symmetrically Server Text and
        # Client Shadow) must be absolutely identical after every half of the
        # synchronization
        #
        # receive text_patches and client_shadow_cksum
        #
        # first check the server shadow cheksum
        # if server_shadows[client_id] is empty ask for it

        client_id = req['client_id']
        client_shadow_cksum = req['client_shadow_cksum']

        server_text = __get_server_text()
        server_shadow = __get_shadow(client_id)
        if server_shadow is None:
            if server_text:
                print("ServerShadowChecksumFailed")
                 # FIXME: Change ServerShadowChecksumFailed to its own type
                res = {
                    'status': 'ERROR',
                    'error_type': 'ServerShadowChecksumFailed',
                    'error_message': 'Shadows got desynced. Sending back the full server shadow',
                    'server_shadow': server_text,
                    }
                __set_shadow(client_id, server_text)
            else:
                print("NoServerShadow")
                res = err_response('NoServerShadow',
                'No shadow found in the server. Send it again')
            #print("NoServerShadow")
            #res = err_response('NoServerShadow',
            #'No shadow found in the server. Send it again')
        else:
            if not server_shadow: # FIXME coverage should show that it should never enter here
                server_shadow_cksum = 0
            else:
                server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
            print("server_shadow_cksum {}".format(server_shadow_cksum))
            #print(server_shadow)

            if client_shadow_cksum != server_shadow_cksum:
                #FIXME what happenson first sync?
                print("ServerShadowChecksumFailed")
                res = {
                    'status': 'ERROR',
                    'error_type': 'ServerShadowChecksumFailed',
                    'error_message': 'Shadows got desynced. Sending back the full server shadow',
                    'server_shadow' : server_shadow
                    }
            else:
                #print("shadows' checksums match")

                diff_obj = diff_match_patch.diff_match_patch()
                diff_obj.Diff_Timeout = DIFF_TIMEOUT

                patches2 = diff_obj.patch_fromText(req['client_patches'])

                server_shadow_patch_results = None
                if not server_shadow:
                    server_shadow_patch_results = diff_obj.patch_apply(
                      patches2, "")
                else:
                    server_shadow_patch_results = diff_obj.patch_apply(
                      patches2, server_shadow)
                shadow_results = server_shadow_patch_results[1]

                # len(set(list)) should be 1 if all elements are the same
                if len(set(shadow_results)) == 1 and shadow_results[0]:
                    # step 5
                    __set_shadow(client_id, server_shadow_patch_results[0])
                    server_text = __get_server_text()


                    server_text_patch_results = None
                    server_text_patch_results = diff_obj.patch_apply(
                          patches2, server_text)
                    text_results = server_text_patch_results[1]

                    if any(text_results):
                        # step 7
                        __set_server_text(server_text_patch_results[0])

                        #
                        # Here starts second half of sync.
                        #

                        print("""#
# Here starts second half of sync.
#""")

                        diff_obj = diff_match_patch.diff_match_patch()
                        diff_obj.Diff_Timeout = DIFF_TIMEOUT

                        # from https://neil.fraser.name/writing/sync/
                        # step 1 & 2
                        # Client Text is diffed against Shadow. This returns a list of edits which
                        # have been performed on Client Text

                        server_shadow = __get_shadow(client_id)
                        server_text = __get_server_text()
                        edits = None
                        if not server_shadow:
                            edits = diff_obj.diff_main("", server_text)
                        else:
                            edits = diff_obj.diff_main(server_shadow, server_text)
                        diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?

                        patches = diff_obj.patch_make(edits)
                        text_patches = diff_obj.patch_toText(patches)

                        if not text_patches:
                            # nothing to update!
                            res = err_response('NoUpdate',
                            'Nothing to update')
                        else:
                            #print("step 2 results: {}".format(text_patches))

                            #step 3
                            #
                            # Client Text is copied over to Shadow. This copy must be identical to
                            # the value of Client Text in step 1, so in a multi-threaded environment
                            # a snapshot of the text should have been taken.
                            server_shadow_cksum = 0
                            if not server_shadow:
                                print("server_shadow: None")
                            else:
                                server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
                            print("server_shadow_cksum {}".format(server_shadow_cksum))
                            #print(server_shadow)

                            __set_shadow(client_id, server_text)

                            res = {
                                'status': 'OK',
                                'client_id': client_id,
                                'server_shadow_cksum': server_shadow_cksum,
                                'text_patches': text_patches,
                                }
                    else:
                        # should I try to patch again?
                        print("FuzzyServerPatchFailed")
                        res = {
                            'status': 'ERROR',
                            'error_type': 'FuzzyServerPatchFailed',
                            'error_message': 'Fuzzy patching failled. Sending back the full server text',
                            'server_text' : server_text
                            }
                else:
                    # I should try to patch again
                    res = err_response('ServerPatchFailed',
                    'Match-Patch failed in server')
    else:
        if not req:
            res = err_response('NoPayload',
            'No payload found in the request')
        elif not 'client_id' in req:
            res = err_response('PayloadMissingAttribute',
            'No client_id found in the request')
        elif not 'client_shadow_cksum' in req:
            res = err_response('PayloadMissingAttribute',
            'No client_shadow_cksum found in the request')
        elif not 'client_patches' in req:
            res = err_response('PayloadMissingAttribute',
            'No client_patches found in the request')
        else:
            print("receive_sync 500")
            abort(500)
    print("response:")
    print(res)
    return flask.jsonify(**res)




def receive_shadow(request):
    #import pdb; pdb.set_trace()
    print("receive_shadow")
    req = request.json
    res = None
    if req and 'client_id' in req and 'client_shadow' in req:
        res = err_response('UnknowErrorSendShadow',
        'Unknown error in receive_shadow')

        __set_shadow(req['client_id'], req['client_shadow'])

        res = {
            'status': 'OK',
            }
    else:
        if not req:
            res = err_response('NoPayload',
            'No payload found in the request')
        elif not 'client_id' in req:
            res = err_response('PayloadMissingAttribute',
            'No client_id found in the request')
        elif not 'client_shadow' in req:
            res = err_response('PayloadMissingAttribute',
            'No client_shadow found in the request')
        else:
            print("receive_shadow 500")
            abort(500)
    print("response:")
    print(res)
    return flask.jsonify(**res)



def err_response(error_type, error_message):
    return {
        'status': 'ERROR',
        'error_type': error_type,
        'error_message': error_message,
        }


def __set_server_text(text):
    with closing(shelve.open(temp_server_file_name)) as d:
        d['server_text'] = text


def __get_server_text():
    with closing(shelve.open(temp_server_file_name)) as d:
        if 'server_text' in d:
            return d['server_text']
        else:
            return ""


def __set_server_shadow(shadows):
    with closing(shelve.open(temp_server_file_name)) as d:
        d['server_shadows'] = shadows


def __set_shadow(client_id, value):
    shadows = __get_server_shadow()
    shadows[client_id] = value
    __set_server_shadow(shadows)


def __get_server_shadow():
    with closing(shelve.open(temp_server_file_name)) as d:
        if 'server_shadows' in d:
            return d['server_shadows']
        else:
            return {}

def __get_shadow(client_id):
    shadows = __get_server_shadow()
    shadow = None
    if client_id in shadows:
        shadow = shadows[client_id]
    return shadow


def get_text(request):
    #import pdb; pdb.set_trace()
    #print("get_text")
    server_text = __get_server_text()

    res = {
        'status': 'OK',
        'server_text': server_text,
        }
    print("response:")
    print(res)
    return flask.jsonify(**res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    args = parser.parse_args()
    client_port = 5002
    if args.port and int(args.port) > 0:
        client_port = int(args.port)

    app.config['DB_PATH'] = db.get_db_path(app.config['DB_FILENAME_FORMAT'], client_port)
    connect_db()
    init_db()
    #print("My ID is {}. Starting up server...".format(app.config['CLIENT_ID']))
    app.run(host='0.0.0.0', port=client_port)
