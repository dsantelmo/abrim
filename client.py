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
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Title of the document</title>

        <meta name="viewport" content="width=device-width, initial-scale=1.0">

    </head>

  <body>
    <header>
        <h1>header</h1>
    </<header>
    <nav>main nav</nav>
    <main>
        <article>
            <header>
              <h1>text title</h1>
              <p>Last modified: <time datetime="2000-01-01T00:00:00Z">on 2000/01/01 at 0:00pm</time>
              </p>
            </header>
            <section>
                <form action="/sync" method="post">
                    <p>
                        <textarea name="client_text" placeholder="Some text here...">"""
    main_form2 = """</textarea>
                    </p>
                    <p>
                        <input type="submit" value="Sync!">
                    </p>
                </form>
            </section>
            <section>
                <form>
                  <textarea name="client_shadow" disabled placeholder="Shadow text...">
"""

    main_form3 = """</textarea>
                </form>
            </section>
        </article>
    </main>
    <nav>recent nav</nav>
    <nav>tags nav<nav>
    <footer>footer</footer>
  </body>
</html>
"""
    with closing(shelve.open(temp_client_file_name)) as d:
        if not 'client_text' in d:
            d['client_text'] = """Bad dog. KO"""
        if not 'client_shadow' in d:
            d['client_shadow'] = """Bad dog. KO"""
        main_form = main_form1 + d['client_text'] + \
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
            print("show_sync 500 A")
            abort(500)

        if not client_text or not client_shadow:
            print("show_sync 500 B")
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
                #step 3
                #
                # Client Text is copied over to Shadow. This copy must be identical to
                # the value of Client Text in step 1, so in a multi-threaded environment
                # a snapshot of the text should have been taken.

                client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()
                # FIXME what happens on first sync?
                print("client_shadow_cksum {}".format(client_shadow_cksum))

                d['client_shadow'] = client_text


                # send text_patches, client_id and client_shadow_cksum

                url = "http://127.0.0.1:5002/send_sync"

                r = send_sync(url, CLIENT_ID, client_shadow_cksum, text_patches)

                print("-------------------")
                try:
                    r_json = r.json()
                    if 'status' in r_json:
                        if not r_json['status'] == u"OK":
                            error_return = "Unknown error in response"
                            if 'error_type' in r_json:
                                if r_json['error_type'] == u"NoServerShadow":
                                    # client sends its shadow:
                                    r_shadow = send_shadow("http://127.0.0.1:5002/send_shadow", CLIENT_ID, d['client_shadow'])
                                    try:
                                        r_shadow_json = r_shadow.json()
                                        if 'status' in r_shadow_json:
                                            if r_shadow_json['status'] == "OK":
                                                return "Shadow updated. Sync Again"
                                            else:
                                                return "ERROR: unable to send_shadow"
                                        else:
                                            return "ERROR: send_shadow response doesn't contain status"
                                    except ValueError, e:
                                        return(r_shadow.text)
                                else:
                                    error_return = "ERROR<br />" + r_json['error_type']
                                    if  'error_message' in r_json:
                                        error_return = error_return + "<br />" + r_json['error_message']
                            return error_return
                        else:
                            print("sync seems to be going OK")
                            print("FIXME: CONTINUE HERE")
                            return("sync OK")
                    else:
                        return "ERROR: send_sync response doesn't contain status"
                    {u'status': u'ERROR', u'error_type': u'NoServerShadow', u'error_message': u'No shadow found in the server. Send it again'}
                except ValueError, e:
                    return(r.text)
            except ValueError:
                print "ValueError"
                return "ERROR: ValueError" #FIXME
            except urllib2.URLError:
                print "URLError"
                return "ERROR: URLError" #FIXME
            except requests.exceptions.ConnectionError:
                print "ConnectionError"
                return "ERROR: ConnectionError" #FIXME


    print("show_sync 500 C")
    abort(500)

def send_sync(url, client_id, client_shadow_cksum, client_patches):
    payload = {
               'client_id': client_id,
               'client_shadow_cksum': client_shadow_cksum,
               'client_patches': client_patches,
              }

    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      data=json.dumps(payload)
      )

def send_shadow(url, client_id, client_shadow):
    payload = {
               'client_id': client_id,
               'client_shadow': client_shadow,
              }

    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      data=json.dumps(payload)
      )

if __name__ == "__main__":
    app.run(port=5001)