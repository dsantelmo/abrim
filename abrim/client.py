#!/usr/bin/env python

from contextlib import closing
import os
import sys
import hashlib
import json
import argparse
from flask import Flask, g, request, redirect, url_for, abort, render_template, flash
import diff_match_patch
import requests
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.utils import config_files
from abrim.utils.common import generate_random_id
from abrim.db import db


app = Flask(__name__)
# Default config:
app.config['APP_NAME'] = "Sync"
app.config['APP_AUTHOR'] = "Abrim"
app.config['BCRYPT_ROUNDS'] = 15
app.config['DIFF_TIMEOUT'] = 0.1
app.config['CLIENT_ID'] = generate_random_id(5)
app.config['MAX_RECURSIVE_COUNT'] = 3
app.config['DB_FILENAME_FORMAT'] = 'abrimsync-{}.sqlite'
app.config['DB_SCHEMA_PATH'] = 'db\\schema.sql'
app.config['URL_FOR_GET_TEXT'] = "http://127.0.0.1:5002/get_text"
app.config['URL_FOR_SEND_SYNC'] = "http://127.0.0.1:5002/send_sync"
app.config['URL_FOR_SEND_SHADOW'] = "http://127.0.0.1:5002/send_shadow"

# Config from files and env vars:
config_files.load_app_config(app)
app.config.from_envvar('ABRIMSYNC_SETTINGS', silent=True)


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
        return show_main_form(app.config['URL_FOR_GET_TEXT'])

@app.route('/sync', methods=['GET', 'POST'])
def __sync():
    if request.method != 'POST':
        abort(404)
    else:
        return _sync(request.form)


@app.teardown_appcontext
def close_db(error):
    db.close_db(g, error)


def connect_db():
    return db.connect_db(app.config['DB_PATH'])


def get_db():
    return db.get_db(g, app.config['DB_PATH'])


def init_db():
    db.init_db(app, g, app.config['DB_PATH'], app.config['DB_SCHEMA_PATH'])


# FIXME: DELETE THIS ------
CLIENT_ID = app.config['CLIENT_ID']
# FIXME: DELETE THIS ------


def __get_content(user_id):
    return db.get_content_or_shadow(g, app.config['DB_PATH'], user_id, user_id, db.CONTENT)


def __get_shadow(user_id):
    return db.get_content_or_shadow(g, app.config['DB_PATH'], user_id, user_id, db.SHADOW)


def __set_content(user_id, value):
    return db.set_content_or_shadow(g, app.config['DB_PATH'], user_id, user_id, value, db.CONTENT)


def __set_shadow(user_id, value):
    return db.set_content_or_shadow(g, app.config['DB_PATH'], user_id, user_id, value, db.SHADOW)


def show_datastore_form():
    table_names = db.get_all_tables(g, app.config['DB_PATH'])
    content= db.get_table_contents(g, app.config['DB_PATH'], table_names)
    #print(content)
    #with closing(__open_datastore()) as d:
    #    temp_string = "<h1>Datastore</h1><h3>" + app.config['DB_PATH'] + "</h3>"
    #    return __print_iter_contents(d, 6, temp_string)
    return render_template('datastore.html', CLIENT_ID=CLIENT_ID, content=content)


from passlib.hash import bcrypt
#hash = bcrypt.encrypt(usersPassword, rounds=app.config['BCRYPT_ROUNDS'])
## Validating a hash
#if bcrypt.verify(usersPassword, hash):


def show_main_form(get_text_url):
    # FIXME: add logging - print("show_main_form")
    client_text = __get_content(CLIENT_ID)
    if client_text is None or client_text == "":
        client_text = ""
        # print("show_main_form: not client_text")
        payload = { 'client_id': CLIENT_ID, }
        try:
            r = requests.post(
              get_text_url,
              headers={'Content-Type': 'application/json'},
              data=json.dumps(payload)
              )
        except requests.exceptions.ConnectionError:
            flash("Server is unreachable", 'error')
            #return redirect(url_for('__main'), code=302)
        else:
            try:
                r_json = r.json()
            except ValueError as e:
                # print("ValueError in show_main_form: {0}".format(e.message))
                flash("Server response error, no JSON", 'error')
                #return redirect(url_for('__main'), code=302)
            else:
                if 'status' in r_json:
                    if (r_json['status'] != "OK"
                        or 'server_text' not in r_json
                        ):
                        return "ERROR: uncontrolled error in the server"
                    else:
                        client_text = r_json['server_text']
                else:
                    return "ERROR: failure contacting the server"
        __set_content(CLIENT_ID, client_text)

    client_shadow = __get_shadow(CLIENT_ID)
    if not client_shadow:
        client_shadow= ""
    return render_template('client.html',
            CLIENT_ID=CLIENT_ID,
            client_text=client_text,
            client_shadow=client_shadow)


def _sync(req_form):
    #if req_form and 'get_text' in req_form:
    #    return get_sync(request.form['client_text'], 0)
    #el
    if req_form and 'send_text' in req_form:
        return send_sync(app.config['URL_FOR_SEND_SYNC'], app.config['URL_FOR_SEND_SHADOW'], request.form['client_text'], 0)
    else:
        flash("Command not recognized", 'error')
        return redirect(url_for('__main'), code=302)


def send_sync(send_sync_url, send_shadow_url, client_text, recursive_count, previously_shadow_updated_from_client=False):
    recursive_count += 1

    if recursive_count > app.config['MAX_RECURSIVE_COUNT']:
        return "MAX_RECURSIVE_COUNT"

    client_shadow = __get_shadow(app.config['CLIENT_ID'])

    if not client_text:
        # nothing to sync!
        flash("nothing to sync...", 'warn')
        return redirect(url_for('__main'), code=302)

    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']

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
        # nothing new to sync in this side. Check the other side for updates
        if not previously_shadow_updated_from_client:
            #flash("no changes", 'warn')
            r = __get_text_payload(app.config['URL_FOR_GET_TEXT'], app.config['CLIENT_ID'])
            try:
                r_json = r.json()
                if 'status' in r_json:
                    if (r_json['status'] != "OK"
                        and r_json['error_type'] != "NoUpdate"
                        and r_json['error_type']  != "FuzzyServerPatchFailed"):
                        pass
                    fixme_text = """
Continue with a function of "Here starts second half of sync" from below
"""
                    return(r.text + fixme_text)
            except ValueError:
                #print("ValueError")
                return(r.text)
        else:
            flash("Sync OK!", 'info')
        return redirect(url_for('__main'), code=302)
    else:
        # changes in this side that need to sync
        # print("step 2 results: {}".format(text_patches))

        try:
            #step 3
            #
            # Client Text is copied over to Shadow. This copy must be identical to
            # the value of Client Text in step 1, so in a multi-threaded environment
            # a snapshot of the text should have been taken.

            client_shadow_cksum = 0
            if not client_shadow:
                # print("client_shadow: None")
                pass
            else:
                #print("client_shadow: " + client_shadow)
                client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
            #print("_____________pre__cksum_______")
            #print(client_shadow_cksum)

            client_shadow = client_text
            __set_content(CLIENT_ID, client_text)
            __set_shadow(CLIENT_ID, client_text)

            # send text_patches, client_id and client_shadow_cksum
            r = __send_sync_payload(send_sync_url, CLIENT_ID, client_shadow_cksum, text_patches)
            try:
                r_json = r.json()
                if 'status' in r_json:
                    if (r_json['status'] != "OK"
                        and r_json['error_type'] != "NoUpdate"
                        and r_json['error_type']  != "FuzzyServerPatchFailed"):
                        # print("__manage_send_sync_error_return")
                        error_return, new_client_shadow = __manage_send_sync_error_return(send_sync_url, send_shadow_url, r_json, CLIENT_ID, recursive_count)
                        __set_content(CLIENT_ID, client_text)
                        __set_shadow(CLIENT_ID, client_text)
                        if new_client_shadow:
                            __set_shadow(CLIENT_ID, new_client_shadow)
                            #print("client shadow updated from the server")
                            error_return = send_sync(send_sync_url, send_shadow_url, __get_content(CLIENT_ID), recursive_count)
                        return error_return
                    else:
                        __set_content(CLIENT_ID, client_text)
                        __set_shadow(CLIENT_ID, client_text)
                        if (r_json['status'] != "OK"
                            and r_json['error_type'] == "NoUpdate"):
                            # no changes so nothing else to do
                            flash("Sync OK!", 'info')
                            return redirect(url_for('__main'), code=302)
                        elif (r_json['status'] != "OK"
                            and r_json['error_type'] == "FuzzyServerPatchFailed"):
                            if 'server_text' in r_json:
                                __set_content(CLIENT_ID, r_json['server_text'])
                                __set_shadow(CLIENT_ID, r_json['server_text'])
                                flash("Fuzzy patch failed. Data loss", 'error')
                                return redirect(url_for('__main'), code=302)
                            else:
                                return "ERROR: malformed server response"
                        else:
                            if ('client_id' in r_json
                                and 'server_shadow_cksum' in r_json
                                and 'text_patches' in r_json
                                ):
                                #
                                # Here starts second half of sync.
                                #
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
                                # receive text_patches and server_shadow_cksum
                                #
                                # first check the client shadow cheksum
                                #
                                client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
                                #print("client_shadow_cksum {}".format(client_shadow_cksum))

                                if client_shadow_cksum != r_json['server_shadow_cksum']:
                                    return "ERROR: client shadow checksum failed"
                                else:
                                    #print("shadows' checksums match")

                                    diff_obj = diff_match_patch.diff_match_patch()
                                    diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']

                                    patches = diff_obj.patch_fromText(r_json['text_patches'])

                                    client_shadow_patch_results = None
                                    client_shadow_patch_results = diff_obj.patch_apply(
                                      patches, client_shadow)
                                    shadow_results = client_shadow_patch_results[1]

                                    # len(set(list)) should be 1 if all elements are the same
                                    if len(set(shadow_results)) == 1 and shadow_results[0]:
                                        # step 5
                                        __set_shadow(
                                            CLIENT_ID,
                                            client_shadow_patch_results[0]
                                        )
                                        # should a break here be catastrophic ??
                                        #
                                        # step 6
                                        client_text_patch_results = None
                                        client_text_patch_results = diff_obj.patch_apply(
                                              patches, client_text)
                                        text_results = client_text_patch_results[1]

                                        if any(text_results):
                                            # step 7
                                            __set_content(CLIENT_ID, client_text_patch_results[0])
                                            #
                                            # Here finishes the full sync.
                                            #
                                        flash("Sync OK!", 'info')
                                        return redirect(url_for('__main'), code=302)
                                    else:
                                        # I should try to patch again
                                        return "ERROR: Match-Patch failed in client"
                            else:
                                return "ERROR: malformed server response"
                else:
                    return "ERROR: send_sync response doesn't contain status"
            except ValueError:
                #print("ValueError")
                return(r.text)
        except ValueError:
            #print("ValueError")
            return "ERROR: ValueError" #FIXME
        except requests.exceptions.ConnectionError:
            #print("ConnectionError")
            #return "ERROR: ConnectionError" #FIXME
            flash("Server is unreachable", 'error')
            return redirect(url_for('__main'), code=302)

    #print("if we have got to here we have some coverage problems...")
    abort(500)


def __manage_send_sync_error_return(send_sync_url, send_shadow_url, r_json, client_id, recursive_count):
    new_client_shadow = None

    client_text = __get_content(client_id)
    if not client_text:
        raise Exception('There should be a client_text by now...')

    client_shadow = __get_shadow(client_id)
    if not client_shadow:
        client_shadow = ""

    error_return = "Unknown error in response"

    if 'error_type' in r_json:
        if r_json['error_type'] == "NoServerShadow":
            #print("NoServerShadow")
            # client sends its shadow:
            r_send_shadow = __send_shadow_payload(send_shadow_url, client_id, client_shadow)
            try:
                r_send_shadow_json = r_send_shadow.json()
                if 'status' in r_send_shadow_json:
                    if r_send_shadow_json['status'] == "OK":
                        #print("Shadow updated from client. Trying to sync again")
                        #flash("Shadow updated from client. Trying to sync again...", 'info')
                        previously_shadow_updated_from_client = True
                        error_return =  send_sync(send_sync_url, send_shadow_url, client_text, recursive_count, previously_shadow_updated_from_client)
                    else:
                        error_return = "ERROR: unable to send_shadow"
                else:
                    error_return = "ERROR: send_shadow response doesn't contain status"
            except ValueError:
                error_return = r_send_shadow.text
        elif r_json['error_type'] == "ServerShadowChecksumFailed":
            #print("ServerShadowChecksumFailed")
            # server sends its shadow:
            if 'server_shadow' in r_json:
                new_client_shadow = r_json['server_shadow']
                #print("Shadow updated from server. Trying to sync again")
                #flash("Shadow updated from server. Trying to sync again...", 'error')
                error_return =  None
            else:
                error_return = "ERROR: unable to update shadow from server"
        else:
            error_return = "ERROR<br />" + r_json['error_type']
            if  'error_message' in r_json:
                error_return = error_return + "<br />" + r_json['error_message']
                error_return = error_return + "<br />" + "FULL MESSAGE:<br />" + json.dumps(r_json)

    return error_return, new_client_shadow


def __requests_post(url, payload):
    return requests.post(
      url,
      headers={'Content-Type': 'application/json'},
      data=json.dumps(payload)
      )


def __send_sync_payload(url, client_id, client_shadow_cksum, client_patches):
    payload = {
               'client_id': client_id,
               'client_shadow_cksum': client_shadow_cksum,
               'client_patches': client_patches,
              }

    #print("__send_sync_payload: " + \
    #        ''.join('{}{}'.format(key, val) for key, val in payload.items()))
    return __requests_post(url, payload)


def __send_shadow_payload(url, client_id, client_shadow):
    payload = {
               'client_id': client_id,
               'client_shadow': client_shadow,
              }

    #print("__send_shadow_payload: " + \
    #        ''.join('{}{}'.format(key, val) for key, val in payload.items()))
    return __requests_post(url, payload)

def __get_text_payload(url, client_id):
    payload = {
               'client_id': client_id,
              }

    #print("__get_text_payload: " + \
    #        ''.join('{}{}'.format(key, val) for key, val in payload.items()))
    return __requests_post(url, payload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port")
    args = parser.parse_args()
    client_port = 5001
    if args.port and int(args.port) > 0:
        client_port = int(args.port)

    app.config['DB_PATH'] = db.get_db_path(app.config['DB_FILENAME_FORMAT'], client_port)
    connect_db()
    init_db()
    #print("My ID is {}. Starting up server...".format(app.config['CLIENT_ID']))
    app.run(host='0.0.0.0', port=client_port)
