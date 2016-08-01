#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for, abort
import diff_match_patch

DIFF_TIMEOUT=0.1
CLIENT_ID='client1'

# set FLASK_APP=client.py
# set FLASK_DEBUG=1
# python -m flask run
app = Flask(__name__)
app.debug = True


#@app.route('/', methods=['POST',])
@app.route('/', methods=['GET', 'POST'])
def __root():
    return redirect(url_for('__main'), code=307) #307 for POST redir

@app.route('/main/', methods=['GET', 'POST'])
def __main():
    if request.method == 'POST':
        pass
    else:
        return show_main_form()

@app.route('/sync', methods=['GET', 'POST'])
def __sync():
    if request.method != 'POST':
        abort(404)
    else:
        return show_sync(request.form['client_text'])


from contextlib import closing
import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure 
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
import tempfile
import os


temp_client_file_name = os.path.join( tempfile.gettempdir(),
  tempfile.gettempprefix() + CLIENT_ID)



def show_main_form():
    main_form = ""
    main_form1 = """
<form action="/sync" method="post">
text:
<textarea name="client_text">"""
    main_form2 = """</textarea>
<br /><br />
shadow
<textarea disabled>
"""

    main_form3 = """</textarea>
<br /><br />
<input type="submit" value="Sync!">
</form>
"""
    with closing(shelve.open(temp_client_file_name)) as d:
        if not 'client_text' in d:
            d['client_text'] = """Bad dog. KO"""
        if not 'client_shadow' in d:
            d['client_shadow'] = """Bad dog. KO"""
        main_form = "In " + temp_client_file_name + " <br /><br />" + \
                    main_form1 + d['client_text'] + \
                    main_form2 + d['client_shadow'] + \
                    main_form3
    return main_form 


import diff_match_patch
import hashlib
import requests
import json
import urllib2
import sys

def show_sync(client_text):
    client_shadow = None
    
    with closing(shelve.open(temp_client_file_name)) as d:
        try:
            client_shadow =  d['client_shadow']
        except KeyError, e:
            abort(500)

        if not client_text or not client_shadow:
            abort(500)
            
        
        diff_obj = diff_match_patch.diff_match_patch()
        diff_obj.Diff_Timeout = DIFF_TIMEOUT

        # from https://neil.fraser.name/writing/sync/
        # step 1 & 2
        # Client Text is diffed against Shadow. This returns a list of edits which
        # have been performed on Client Text


        edits = diff_obj.diff_main(client_shadow, client_text)
        diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?

        patches = diff_obj.patch_make(edits)
        text_patches = diff_obj.patch_toText(patches)

        if not text_patches:
            return("nothing to update!")
        else:
            print ("step 2 results: {}".format(text_patches))

            try:
                #
                #step 3
                #
                # Client Text is copied over to Shadow. This copy must be identical to
                # the value of Client Text in step 1, so in a multi-threaded environment
                # a snapshot of the text should have been taken.
                #
                client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()
                # FIXME what happens on first sync?
                print("client_shadow_cksum {}".format(client_shadow_cksum))
                #
                d['client_shadow'] = client_text

                url = "http://127.0.0.1:5002/send_sync"
                payload = {
                           'client_id': CLIENT_ID,
                           'client_shadow_cksum': client_shadow_cksum,
                           'client_patches': text_patches,
                          }
                print(payload)
                ok = requests.post(
                  url,
                  headers={'Content-Type': 'application/json'},
                  data=json.dumps(payload)
                  )
                #json.loads(urllib2.urlopen(url + '/send_sync').read())

                print ok
                return "ok"
            except ValueError:
                print "ValueError"
                return "ERROR: ValueError" #FIXME
            except urllib2.URLError:
                print "URLError"
                return "ERROR: URLError" #FIXME
            except requests.exceptions.ConnectionError:
                print "ConnectionError"
                return "ERROR: ConnectionError" #FIXME

    abort(500)


if __name__ == "__main__":
    app.run(port=5001)