#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, redirect, url_for, abort, render_template
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
app.config.from_object(__name__)
app.config.from_pyfile('abrim.cfg') #FIXME use instance folders
app.config.from_envvar('ABRIM_SETTINGS', silent=True)


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

def __open_datastore():
    try:
        return shelve.open(temp_client_file_name)
    except:
        return None


def __get_client_attribute(client_id, attrib):
    result = None
    with closing(__open_datastore()) as d:
        if client_id in d and attrib in d[client_id]:
            result = d[client_id][attrib]
        else:
            print("no contents of " + attrib + " for " + client_id)
            if not client_id in d:
                d[client_id] = {}
    return result

def __set_client_attribbute(client_id, attrib, value):
    result = False
    with closing(__open_datastore()) as d:
        if not client_id in d:
            d[client_id] = {}
        temp_client = d[client_id]
        temp_client.update({attrib : value})
        d[client_id] = temp_client
        return True


def show_datastore_form():
    with closing(__open_datastore()) as d:
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
    client_text = __get_client_attribute(CLIENT_ID, 'client_text')
    if not client_text:
        client_text = ""
    client_shadow = __get_client_attribute(CLIENT_ID, 'client_shadow')
    if not client_shadow:
        client_shadow= ""
    return render_template('client.html',
            CLIENT_ID=CLIENT_ID,
            client_text=client_text,
            client_shadow=client_shadow)


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

    client_shadow = __get_client_attribute(CLIENT_ID, 'client_shadow')

    if not client_text:
        # nothing to update!
        return redirect(url_for('__main'), code=302)

    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = DIFF_TIMEOUT

    # from https://neil.fraser.name/writing/sync/
    # step 1 & 2
    # Client Text is diffed against Shadow. This returns a list of edits which
    # have been performed on Client Text

    edits = None
    if not client_shadow:
        edits = diff_obj.diff_main("", client_text)
    else:
        edits = diff_obj.diff_main(client_shadow, client_text)
    diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?

    patches = diff_obj.patch_make(edits)
    text_patches = diff_obj.patch_toText(patches)

    if not text_patches:
        # nothing to update!
        return redirect(url_for('__main'), code=302)
    else:
        #print ("step 2 results: {}".format(text_patches))

        try:
            #step 3
            #
            # Client Text is copied over to Shadow. This copy must be identical to
            # the value of Client Text in step 1, so in a multi-threaded environment
            # a snapshot of the text should have been taken.

            client_shadow_cksum = 0
            if not client_shadow:
                print("client_shadow: None")
            else:
                #print("client_shadow: " + client_shadow)
                client_shadow_cksum =  hashlib.md5(client_shadow).hexdigest()
            #print("_____________pre__cksum_______")
            #print(client_shadow_cksum)

            __set_client_attribbute(CLIENT_ID, 'client_text', client_text)
            __set_client_attribbute(CLIENT_ID, 'client_shadow', client_shadow)

            # send text_patches, client_id and client_shadow_cksum
            url = "http://127.0.0.1:5002/send_sync"
            r = __send_sync(url, CLIENT_ID, client_shadow_cksum, text_patches)
            try:
                r_json = r.json()
                if 'status' in r_json:
                    if not r_json['status'] == u"OK":
                        #print("__manage_error_return")
                        error_return, new_client_shadow = __manage_error_return(r_json, CLIENT_ID, recursive_count)
                        __set_client_attribbute(CLIENT_ID, 'client_text', client_text)
                        __set_client_attribbute(CLIENT_ID, 'client_shadow', client_text)
                        if new_client_shadow:
                            __set_client_attribbute(CLIENT_ID, 'client_shadow', new_client_shadow)
                            error_return = show_sync(__get_client_attribute(CLIENT_ID, 'client_text'), recursive_count)
                        return error_return
                    else:
                        __set_client_attribbute(CLIENT_ID, 'client_text', client_text)
                        __set_client_attribbute(CLIENT_ID, 'client_shadow', client_text)
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


def __manage_error_return(r_json, client_id, recursive_count):
    new_client_shadow = None

    client_text = __get_client_attribute(client_id, 'client_text')
    if not client_text:
        print("no text in __manage_error_return")

    client_shadow = __get_client_attribute(client_id, 'client_shadow')
    if not client_shadow:
        print("no shadow in __manage_error_return")

    error_return = "Unknown error in response"

    if 'error_type' in r_json:
        if r_json['error_type'] == u"NoServerText":
            print("NoServerText")
            # client sends its text:
            r_send_text = __send_text("http://127.0.0.1:5002/send_text", client_id, client_text, client_shadow)
            try:
                r_send_text_json = r_send_text.json()
                if 'status' in r_send_text_json:
                    if r_send_text_json['status'] == "OK":
                        print("Text updated from client. Trying to sync again")
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
            r_send_shadow = __send_shadow("http://127.0.0.1:5002/send_shadow", client_id, client_shadow)
            try:
                r_send_shadow_json = r_send_shadow.json()
                if 'status' in r_send_shadow_json:
                    if r_send_shadow_json['status'] == "OK":
                        print("Shadow updated from client. Trying to sync again")
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
                print("Shadow updated from server. Trying to sync again")
                error_return =  show_sync(client_text, recursive_count)
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
