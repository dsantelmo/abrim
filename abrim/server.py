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
    abort(404)

@app.route('/datastore')
def __datastore():
    if request.method != 'GET':
        abort(404)
    else:
        return show_datastore_form()



@app.route('/send_sync', methods=['POST'])
def __sync():
    if request.method != 'POST':
        abort(404)
    else:
        return send_sync(request)


@app.route('/send_text', methods=['POST'])
def __text():
    if request.method != 'POST':
        abort(404)
    else:
        return send_text(request)


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



import diff_match_patch
import hashlib
import requests
import json

def send_sync(request):
    #import pdb; pdb.set_trace()
    print("send_sync")
    req = request.json
    res = err_response('UnknownError', 'Not controlled error in server')
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
        server_shadows = {}
        with closing(shelve.open(temp_server_file_name)) as d:
            if 'server_text' in d:
                server_text = d['server_text']
            if not 'server_shadows' in d:
                d['server_shadows'] = {}
            else:
                server_shadows = d['server_shadows']

        # first check the server shadow cheksum
        # if server_shadows[client_id] is empty ask for it

        client_id = req['client_id']
        client_shadow_cksum = req['client_shadow_cksum']

        if not server_text:
            print("NoServerText")
            res = err_response('NoServerText',
            'No text found in the server. Send it again')
        elif not client_id in server_shadows:
            print("NoServerShadow")
            res = err_response('NoServerShadow',
            'No shadow found in the server. Send it again')
        else:
            server_shadow = server_shadows[client_id]
            if not server_shadow:
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
                results = server_shadow_patch_results[1]

                # len(set(list)) should be 1 if all elements are the same
                if len(set(results)) == 1 and results[0]:
                    # step 5
                    with closing(shelve.open(temp_server_file_name)) as d:
                        server_shadows = d['server_shadows']
                        server_shadows[client_id] = server_shadow_patch_results[0]
                        d['server_shadows'] = server_shadows
                        # should a break here be catastrophic ??
                        #
                        # step 6
                        server_text = d['server_text']

                        edits = diff_obj.diff_main(server_text, server_shadow_patch_results[0])
                        diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?

                        server_text_patches = diff_obj.patch_make(edits)

                        server_text_patch_results = diff_obj.patch_apply(
                          server_text_patches, server_text)
                        server_text_patches_results = server_shadow_patch_results[1]

                        # len(set(list)) should be 1 if all elements are the same
                        if len(set(server_text_patches_results)) == 1 and server_text_patches_results[0]:
                            #
                            #step 7
                            d['server_text'] = server_text_patch_results[0]
                            res = { 'status': 'OK', }
                        else:
                            # I should try to patch again
                            res = err_response('ServerPatchFailed',
                            'Match-Patch failed in server')
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
            print("send_sync 500")
            abort(500)
    print("response:")
    print(res)
    return flask.jsonify(**res)



def send_text(request):
    #import pdb; pdb.set_trace()
    print("send_text")
    req = request.json
    res = None
    if req and 'client_id' in req and 'client_text' in req:
        server_shadows = None

        res = err_response('UnknowErrorSendShadow',
        'Unknown error in send_text')

        with closing(shelve.open(temp_server_file_name)) as d:
            if not 'server_text' in d:
                d['server_text'] = req['client_text']

            if not 'server_shadows' in d:
                d['server_shadows'] = {}
            server_shadows = d['server_shadows']

            client_id = req['client_id']
            server_shadows[client_id] = req['client_shadow']
            d['server_shadows'] = server_shadows

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
            print("send_text 500")
            abort(500)
    print("response:")
    print(res)
    return flask.jsonify(**res)



def send_shadow(request):
    #import pdb; pdb.set_trace()
    print("send_shadow")
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

            #print("saving shadow from " + req['client_id'])
            #print("----")
            #print(req['client_shadow'])
            #print("----")
            client_id = req['client_id']
            server_shadows[client_id] = req['client_shadow']
            d['server_shadows'] = server_shadows

            #d['server_text'] = req['client_shadow']

            #print("send_shadow: " + \
            #        ''.join('{}{}'.format(key, val) for key, val in d.items()))

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
