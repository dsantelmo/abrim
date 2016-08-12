#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for, abort
import diff_match_patch
import random
import string

DIFF_TIMEOUT = 0.1
CLIENT_ID = ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(5))
MAX_RECURSIVE_COUNT = 3

# set FLASK_APP=client.py
# set FLASK_DEBUG=1
# python -m flask run
app = Flask(__name__)
app.debug = True


#@app.route('/', methods=['POST',])
@app.route('/', methods=['GET', 'POST'])
def __root():
    return redirect(url_for('__main'), code=307) #307 for POST redir


@app.route('/datastore')
def __datastore():
    if request.method != 'GET':
        abort(404)
    else:
        return show_datastore_form()

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
        return show_sync(request.form['client_text'], 0)




from contextlib import closing
import shelve
# FIXME Warning Because the shelve module is backed by pickle, it is insecure 
# to load a shelf from an untrusted source. Like with pickle, loading a shelf
# can execute arbitrary code.
import tempfile
import os


temp_client_file_name = os.path.join( tempfile.gettempdir(),
  tempfile.gettempprefix() + "abrim_client_datastore")





def show_datastore_form():
    with closing(shelve.open(temp_client_file_name)) as d:
        temp_string = "<h1>Datastore</h1><h3>" + temp_client_file_name + "</h3>"
        return __print_iter_contents(d, 6, temp_string)

def __print_iter_contents(iter, depth, temp_string):
    if depth > 0:
        for k, element in iter.iteritems():
            if isinstance(element, dict):
                temp_string = temp_string + "<li><b>{0} :</b></li>".format(k)
                temp_string = temp_string + "<ul>"
                temp_string = __print_iter_contents(element, depth - 1, temp_string)
                temp_string = temp_string + "</ul>"
            else:
                temp_string = temp_string + "<li><b>{0}</b> : {1}</li>".format(k, element)
    return temp_string







def show_main_form():
    main_form = ""
    main_form1 = """
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Title of the document</title>

        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <style type="text/css">

        html {
          font-size: medium;
        }

        body {
          background-color: #fffff6;
          color: #330;
          font-family: georgia, times, serif;
          margin: 2rem auto;
          max-width: 40em;
          padding: 0 2em;
          width: auto;
          font-size: 1rem;
          line-height: 1.4;
        }

        a {
          color: #1e6b8c;
          font-size: 1em;
          text-decoration: none;
          transition-delay: 0.1s;
          transition-duration: 0.3s;
          transition-property: color, background-color;
          transition-timing-function: linear;
        }

        a:visited {
          color: #6f32ad;
          font-size: 1em;
        }

        a:hover {
          background: #f0f0ff;
          font-size: 1em;
          text-decoration: underline;
        }

        a:active {
          background-color: #427fed;
          color: #fffff6;
          color: white;
          font-size: 1em;
        }

        h1,
        h2,
        h3,
        h4,
        h5,
        h6 {
          color: #703820;
          font-weight: bold;
          line-height: 1.2;
          margin-bottom: 0.5em;
          margin-top: 1em;
        }

        h1 {
          font-size: 2.2em;
          text-align: center;
        }

        h2 {
          font-size: 1.8em;
          border-bottom: solid 0.1rem #703820;
        }

        h3 {
          font-size: 1.5em;
        }

        h4 {
          font-size: 1.3em;
          text-decoration: underline;
        }

        h5 {
          font-size: 1.2em;
          font-style: italic;
        }

        h6 {
          font-size: 1.1em;
          margin-bottom: 0.5rem;
        }

        pre,
        code,
        xmp {
          font-family: courier;
          font-size: 1rem;
          line-height: 1.4;
          white-space: pre-wrap;
        }
        </style>

    </head>

  <body>
    <header>
        <h1>Main</h1>
    </<header>
    <nav>User: """ + CLIENT_ID + """ || <b>main</b> - <a href="/datastore">datastore</a></nav>
    <main>
        <article>
            <header>
              <h1>...</h1>
              <p>Last modified: <time datetime="2000-01-01T00:00:00Z">on 2000/01/01 at 0:00pm</time>
              </p>
            </header>
            <section>
                <form autocomplete="off" action="/sync" method="post">
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
                <form autocomplete="off">
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
        client_text = ""
        client_shadow = ""
        if CLIENT_ID in d and 'client_text' in d[CLIENT_ID]:
            client_text = d[CLIENT_ID]['client_text']
        else:
            print("no client_text for " + CLIENT_ID)
            print(d)
        if CLIENT_ID in d and 'client_shadow' in d[CLIENT_ID]:
            client_shadow = d[CLIENT_ID]['client_shadow']
        else:
            print("no client_shadow for " + CLIENT_ID)
        main_form = main_form1 + client_text + \
                    main_form2 + client_shadow + \
                    main_form3
    return main_form 


import diff_match_patch
import hashlib
import requests
import json
import urllib2
import sys

def show_sync(client_text, recursive_count):

    recursive_count += 1

    if recursive_count > MAX_RECURSIVE_COUNT:
        return "MAX_RECURSIVE_COUNT"

    client_shadow = None

    with closing(shelve.open(temp_client_file_name)) as d:
        try:
            client = d[CLIENT_ID]
            client_shadow = client['client_shadow']
        except KeyError, e:
            if not CLIENT_ID in d:
                d[CLIENT_ID] = {}
            if not 'client_shadow' in d[CLIENT_ID]:
                client_shadow = ""
                temp_client = d[CLIENT_ID]
                temp_client.update({'client_shadow' : client_shadow})
                d[CLIENT_ID] = temp_client

        if not client_text:
            return("nothing to update!")


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

                print("_____________pre__cksum_______")
                client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()
                print(client_shadow_cksum)

                d[CLIENT_ID] = {'client_text' : client_text,
                                'client_shadow' : client_text, }

                # send text_patches, client_id and client_shadow_cksum

                url = "http://127.0.0.1:5002/send_sync"

                r = __send_sync(url, CLIENT_ID, client_shadow_cksum, text_patches)

                try:
                    r_json = r.json()
                    if 'status' in r_json:
                        if not r_json['status'] == u"OK":
                            print("__manage_error_return")
                            error_return, new_client_shadow = __manage_error_return(r_json, CLIENT_ID, d[CLIENT_ID], recursive_count)
                            if new_client_shadow:
                                temp_client = d[CLIENT_ID]
                                print("_____________pre______________")
                                print(d[CLIENT_ID]['client_shadow'])
                                temp_client.update({'client_shadow' : new_client_shadow})
                                d[CLIENT_ID] = temp_client
                                print("_____________post_____________")
                                print(d[CLIENT_ID]['client_shadow'])
                                print("______________________________")
                                print("new_client_shadow -> show_sync")
                                print("______________________________")
                                error_return = show_sync(d[CLIENT_ID]['client_text'], recursive_count)
                            return error_return
                        else:
                            print("sync seems to be going OK")
                            print("FIXME: CONTINUE HERE")
                            return redirect(url_for('__main'), code=302)
                    else:
                        return "ERROR: send_sync response doesn't contain status"
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


#def __get_client_value(client_id, value):
#    return_value = None
#
#    with closing(shelve.open(temp_client_file_name)) as d:
#        try:
#            client = d[client_id]
#            return_value = client[value]
#        except KeyError, e:
#            pass
#    return return_value


def __manage_error_return(r_json, CLIENT_ID, client, recursive_count):
    client_text = client['client_text']
    client_shadow = client['client_shadow']
    new_client_shadow = None

    error_return = "Unknown error in response"

    if 'error_type' in r_json:
        if r_json['error_type'] == u"NoServerText":
            print("NoServerText")
            # client sends its text:
            r_send_text = __send_text("http://127.0.0.1:5002/send_text", CLIENT_ID, client_text, client_shadow)
            try:
                r_send_text_json = r_send_text.json()
                if 'status' in r_send_text_json:
                    if r_send_text_json['status'] == "OK":
                        #error_return =  "Text updated from client. Sync Again" #FIXME create a recursive function counting tries
                        error_return = show_sync(client_text, recursive_count)
                    else:
                        error_return = "ERROR: unable to send_text"
                else:
                    error_return =  "ERROR: send_text response doesn't contain status"
            except ValueError, e:
                error_return = r_send_text.text
        elif r_json['error_type'] == u"NoServerShadow":
            print("NoServerShadow")
            # client sends its shadow:
            r_send_shadow = __send_shadow("http://127.0.0.1:5002/send_shadow", CLIENT_ID, client_shadow)
            try:
                r_send_shadow_json = r_send_shadow.json()
                if 'status' in r_send_shadow_json:
                    if r_send_shadow_json['status'] == "OK":
                        #error_return = "Shadow updated from client. Sync Again" #FIXME create a recursive function counting tries
                        error_return =  show_sync(client_text, recursive_count)
                    else:
                        error_return = "ERROR: unable to send_shadow"
                else:
                    error_return = "ERROR: send_shadow response doesn't contain status"
            except ValueError, e:
                error_return = r_send_shadow.text
        elif r_json['error_type'] == u"ServerShadowChecksumFailed":
            print("ServerShadowChecksumFailed")
            # server sends its shadow:
            if 'server_shadow' in r_json:
                new_client_shadow = r_json['server_shadow']
                error_return = "Shadow updated from server. Sync Again" #FIXME create a recursive function counting tries
            else:
                error_return = "ERROR: unable to update shadow from server"
        else:
            error_return = "ERROR<br />" + r_json['error_type']
            if  'error_message' in r_json:
                error_return = error_return + "<br />" + r_json['error_message']
                error_return = error_return + "<br />" + "FULL MESSAGE:<br />" + json.dumps(r_json)

    return error_return, new_client_shadow


def __send_sync(url, client_id, client_shadow_cksum, client_patches):
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

def __send_text(url, client_id, client_text, client_shadow):
    payload = {
               'client_id': client_id,
               'client_text': client_text,
               'client_shadow': client_shadow,
              }

    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      data=json.dumps(payload)
      )

def __send_shadow(url, client_id, client_shadow):
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