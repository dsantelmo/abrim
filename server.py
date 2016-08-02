#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for, abort
import flask
import diff_match_patch

DIFF_TIMEOUT=0.1

# set FLASK_APP=client.py
# set FLASK_DEBUG=1
# python -m flask run
app = Flask(__name__)
app.debug = True


#@app.route('/', methods=['POST',])
@app.route('/', methods=['GET', 'POST'])
def __root():
    return show_main_form()


@app.route('/send_sync', methods=['POST'])
def __sync():
    if request.method != 'POST':
        abort(404)
    else:
        return send_sync(request)


@app.route('/send_shadow', methods=['POST'])
def __shadow():
    if request.method != 'POST':
        abort(404)
    else:
        return send_shadow(request)



from contextlib import closing
import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure 
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
import tempfile
import os

SERVER_ID='server1'

temp_server_file_name = os.path.join( tempfile.gettempdir(),
  tempfile.gettempprefix() + SERVER_ID)



def show_main_form():
    return "Hi! I'm a server" 


import diff_match_patch
import hashlib
import requests
import json

def send_sync(request):
    req = request.json
    res = None
    if req and 'client_id' in req and 'client_shadow_cksum' in req and 'client_patches' in req:

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
        server_text = None
        server_shadows = None
        with closing(shelve.open(temp_server_file_name)) as d:
            if not 'server_text' in d:
                d['server_text'] = ""
            if not 'server_shadows' in d:
                d['server_shadows'] = {}
            server_text = d['server_text']
            server_shadows = d['server_shadows']

        # first check the server shadow cheksum
        # if server_shadows[client_id] is empty ask for it

        client_id = req['client_id']

        if not client_id in server_shadows:
            res = err_response('NoServerShadow',
            'No shadow found in the server. Send it again')
        else:

            print("FIXME: CONTINUE HERE")

        #    print("Shadow received. Now you can sync!")
        #    server_shadows[client_id] = client_shadow
        #else:
        #    server_shadow_cksum = hashlib.md5(
        #      server_shadows[client_id]).hexdigest()
        #    print("server_shadow_cksum {}".format(server_shadow_cksum))
        #    if client_shadow_cksum != server_shadow_cksum:
        #        #FIXME what happenson first sync?
        #        print("too bad! Shadows got desynced. "
        #              "I'm sending back ALLserver shadow text, "
        #              "use it a your client shadow")
        #        print(server_shadows[client_id])
        #        #clients updates its shadow AND text:
        #        print("DATALOSS on latest client text. "
        #          "Updating with server text")
        #        client_shadow = server_shadows[client_id]
        #        client_text = client_shadow
        #
        #


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
        elif not 'client_shadow_cksum' in req:
            res = err_response('PayloadMissingAttribute', 
            'No client_shadow_cksum found in the request')
        elif not 'client_patches' in req:
            res = err_response('PayloadMissingAttribute', 
            'No client_patches found in the request')
        else:
            print("send_sync 500")
            abort(500)
    print("response:")
    print(res)
    return flask.jsonify(**res)






def send_shadow(request):
    req = request.json
    res = None
    if req and 'client_id' in req and 'client_shadow' in req:

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
        server_shadows = None

        res = err_response('UnknowErrorSendShadow',
        'Unknown error in send_shadow')

        with closing(shelve.open(temp_server_file_name)) as d:
            if not 'server_shadows' in d:
                d['server_shadows'] = {}
            server_shadows = d['server_shadows']

            # first check the server shadow cheksum
            # if server_shadows[client_id] is empty ask for it

            print("saving shadow from " + req['client_id'])
            print("----")
            print(req['client_shadow'])
            print("----")
            client_id = req['client_id']
            server_shadows[client_id] = req['client_shadow']
            d['server_shadows'] = server_shadows

            print d['server_shadows']

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
            print("send_shadow 500")
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




if __name__ == "__main__":
    app.run(port=5002)