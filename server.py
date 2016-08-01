#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for, abort
import diff_match_patch

DIFF_TIMEOUT=0.1

# set FLASK_APP=client.py
# set FLASK_DEBUG=1
# python -m flask run
app = Flask(__name__)
app.debug = True



# return flask.jsonify(**f)
#    return jsonify(username=g.user.username,
#                   email=g.user.email,
#                   id=g.user.id)
#


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


from contextlib import closing
import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure 
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
import tempfile
import os

SERVER_ID='server1'

temp_client_file_name = os.path.join( tempfile.gettempdir(),
  tempfile.gettempprefix() + SERVER_ID)



def show_main_form():
    return "Hi! I'm a server" 


import diff_match_patch
import hashlib
import requests
import json

def send_sync(request):
    r = request.json
    print r
    if r:
        print r['client_id']
        print r['client_shadow_cksum']
        print r['client_patches']
        return_print = r['client_id'] + "<br />"
        return_print = return_print + r['client_shadow_cksum'] + "<br />"
        return_print = return_print + r['client_patches'] + "<br />"
        return return_print

    abort(500)


if __name__ == "__main__":
    app.run(port=5002)