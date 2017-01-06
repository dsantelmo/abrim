#!/usr/bin/env python

from contextlib import closing
import os
import sys
import hashlib
import json
import logging
import diff_match_patch
import requests
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from abrim.db import db


def step_1_create_diff(item_text, item_shadow, diff_timeout):
    if item_text is None or item_shadow is None:
        return None
    diff_obj = diff_match_patch.diff_match_patch()
    diff_obj.Diff_Timeout = diff_timeout
    diff = diff_obj.diff_main(item_shadow, item_text)
    diff_obj.diff_cleanupSemantic(diff) # FIXME: optional?
    return diff


def step_2_create_edits(diff):
    diff_obj = diff_match_patch.diff_match_patch()
    patches = diff_obj.patch_make(diff)
    text_patches = diff_obj.patch_toText(diff)
    return text_patches

def _get_or_create_shadow(user_id, node_id, item_id, client_text):
    results = db.get_shadow(user_id, node_id, item_id)
    if results is None:
        shadow_id = db.create_shadow(user_id, node_id, item_id, client_text)
        results = (shadow_id, client_text, 0, 0)
    return results

def client_sync(user_id, node_id, item_id, client_text, diff_timeout):
    shadow_id, shadow, client_ver, server_ver = _get_or_create_shadow(user_id, node_id, item_id, client_text)
    diff = step_1_create_diff(client_text, shadow, diff_timeout)
    text_patches = step_2_create_edits(diff)





### #
### # Sync stuff
### #
###
### def items_send_post(client_text, recursive_count, previously_shadow_updated_from_client=False):
###     """send a new client text to the server part"""
###     recursive_count += 1
###
###     if recursive_count > app.config['MAX_RECURSIVE_COUNT']:
###         return "MAX_RECURSIVE_COUNT"
###
###     client_shadow = db.get_shadow(app.config['CLIENT_ID'])
###
###     if not client_text:
###         # nothing to sync!
###         flash("nothing to sync...", 'warn')
###         return redirect(url_for('__main'), code=302)
###
###     # from https://neil.fraser.name/writing/sync/
###     # step 1 & 2
###     # Client Text is diffed against Shadow. This returns a list of edits which
###     # have been performed on Client Text
###
###     diff = step_1_create_diff(client_text, client_shadow, app.config['DIFF_TIMEOUT'])
###     text_patches = step_2_create_edits(diff)
###
###     if not text_patches:
###         # nothing new to sync in this side. Check the other side for updates
###         if not previously_shadow_updated_from_client:
###             #flash("no changes", 'warn')
###             r = items_send_get("NODE_ID", "this_should_be_the_item_id")
###             try:
###                 r_json = r.json()
###                 if 'status' in r_json:
###                     if (r_json['status'] != "OK"
###                         and r_json['error_type'] != "NoUpdate"
###                         and r_json['error_type']  != "FuzzyServerPatchFailed"):
###                         pass
###                     fixme_text = """Continue with a function of "Here starts second half of sync" from below"""
###                     return(r.text + fixme_text)
###             except ValueError:
###                 #print("ValueError")
###                 return(r.text)
###         else:
###             flash("Sync OK!", 'info')
###         return redirect(url_for('__main'), code=302)
###     else:
###         # changes in this side that need to sync
###         # print("step 2 results: {}".format(text_patches))
###
###         try:
###             #step 3
###             #
###             # Client Text is copied over to Shadow. This copy must be identical to
###             # the value of Client Text in step 1, so in a multi-threaded environment
###             # a snapshot of the text should have been taken.
###
###             client_shadow_cksum = 0
###             if not client_shadow:
###                 # print("client_shadow: None")
###                 pass
###             else:
###                 #print("client_shadow: " + client_shadow)
###                 client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
###             #print("_____________pre__cksum_______")
###             #print(client_shadow_cksum)
###
###             client_shadow = client_text
###             db.set_content(app.config['CLIENT_ID'], client_text)
###             db.set_shadow(app.config['CLIENT_ID'], client_text)
###
###             # send text_patches, client_id and client_shadow_cksum
###             r = __items_send_post(client_shadow_cksum, text_patches)
###             try:
###                 r_json = r.json()
###                 if 'status' in r_json:
###                     if (r_json['status'] != "OK"
###                         and r_json['error_type'] != "NoUpdate"
###                         and r_json['error_type']  != "FuzzyServerPatchFailed"):
###                         # print("__manage_send_sync_error_return")
###                         error_return, new_client_shadow = __manage_send_sync_error_return(r_json, recursive_count)
###                         db.set_content(app.config['CLIENT_ID'], client_text)
###                         db.set_shadow(app.config['CLIENT_ID'], client_text)
###                         if new_client_shadow:
###                             db.set_shadow(app.config['CLIENT_ID'], new_client_shadow)
###                             #print("client shadow updated from the server")
###                             error_return = items_send_post(db.get_content(app.config['CLIENT_ID'], "FIXME"), recursive_count)
###                         return error_return
###                     else:
###                         db.set_content(app.config['CLIENT_ID'], client_text)
###                         db.set_shadow(app.config['CLIENT_ID'], client_text)
###                         if (r_json['status'] != "OK"
###                             and r_json['error_type'] == "NoUpdate"):
###                             # no changes so nothing else to do
###                             flash("Sync OK!", 'info')
###                             return redirect(url_for('__main'), code=302)
###                         elif (r_json['status'] != "OK"
###                             and r_json['error_type'] == "FuzzyServerPatchFailed"):
###                             if 'server_text' in r_json:
###                                 db.set_content(app.config['CLIENT_ID'], r_json['server_text'])
###                                 db.set_shadow(app.config['CLIENT_ID'], r_json['server_text'])
###                                 flash("Fuzzy patch failed. Data loss", 'error')
###                                 return redirect(url_for('__main'), code=302)
###                             else:
###                                 return "ERROR: malformed server response"
###                         else:
###                             if ('client_id' in r_json
###                                 and 'server_shadow_cksum' in r_json
###                                 and 'text_patches' in r_json
###                                 ):
###                                 #
###                                 # Here starts second half of sync.
###                                 #
###                                 # FIXME: create atomicity
###                                 #
###                                 # steps 4 (atomic with 5, 6 & 7)
###                                 #
###                                 # The edits are applied to Server Text on a best-effort basis
###                                 # Server Text is updated with the result of the patch. Steps 4 and 5
###                                 # must be atomic, but they do not have to be blocking; they may be
###                                 # repeated until Server Text stays still long enough.
###                                 #
###                                 # Client Text and Server Shadow (or symmetrically Server Text and
###                                 # Client Shadow) must be absolutely identical after every half of the
###                                 # synchronization
###                                 #
###                                 # receive text_patches and server_shadow_cksum
###                                 #
###                                 # first check the client shadow cheksum
###                                 #
###                                 client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
###                                 #print("client_shadow_cksum {}".format(client_shadow_cksum))
###
###                                 if client_shadow_cksum != r_json['server_shadow_cksum']:
###                                     return "ERROR: client shadow checksum failed"
###                                 else:
###                                     #print("shadows' checksums match")
###
###                                     diff_obj = diff_match_patch.diff_match_patch()
###                                     diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                                     patches = diff_obj.patch_fromText(r_json['text_patches'])
###
###                                     client_shadow_patch_results = None
###                                     client_shadow_patch_results = diff_obj.patch_apply(
###                                       patches, client_shadow)
###                                     shadow_results = client_shadow_patch_results[1]
###
###                                     # len(set(list)) should be 1 if all elements are the same
###                                     if len(set(shadow_results)) == 1 and shadow_results[0]:
###                                         # step 5
###                                         db.set_shadow(app.config['CLIENT_ID'], client_shadow_patch_results[0])
###                                         # should a break here be catastrophic ??
###                                         #
###                                         # step 6
###                                         client_text_patch_results = None
###                                         client_text_patch_results = diff_obj.patch_apply(
###                                               patches, client_text)
###                                         text_results = client_text_patch_results[1]
###
###                                         if any(text_results):
###                                             # step 7
###                                             db.set_content(app.config['CLIENT_ID'], client_text_patch_results[0])
###                                             #
###                                             # Here finishes the full sync.
###                                             #
###                                         flash("Sync OK!", 'info')
###                                         return redirect(url_for('__main'), code=302)
###                                     else:
###                                         # I should try to patch again
###                                         return "ERROR: Match-Patch failed in client"
###                             else:
###                                 return "ERROR: malformed server response"
###                 else:
###                     return "ERROR: send_sync response doesn't contain status"
###             except ValueError:
###                 #print("ValueError")
###                 return(r.text)
###         except ValueError:
###             #print("ValueError")
###             return "ERROR: ValueError" #FIXME
###         except requests.exceptions.ConnectionError:
###             #print("ConnectionError")
###             #return "ERROR: ConnectionError" #FIXME
###             flash("Server is unreachable", 'error')
###             return redirect(url_for('__main'), code=302)
###
###     # if we have got to here we have some coverage problems...
###     log.critical("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###     abort(500)
###
###
### def __manage_send_sync_error_return(r_json, recursive_count):
###     new_client_shadow = None
###
###     client_text = db.get_content(app.config['CLIENT_ID'], "FIXME")
###     if not client_text:
###         raise Exception('There should be a client_text by now...')
###
###     client_shadow = db.get_shadow(app.config['CLIENT_ID'])
###     if not client_shadow:
###         client_shadow = ""
###
###     error_return = "Unknown error in response"
###
###     if 'error_type' in r_json:
###         if r_json['error_type'] == "NoServerShadow":
###             #print("NoServerShadow")
###             # client sends its shadow:
###             r_send_shadow = __send_shadow_payload("this_should_be_the_item_id", client_shadow)
###             try:
###                 r_send_shadow_json = r_send_shadow.json()
###                 if 'status' in r_send_shadow_json:
###                     if r_send_shadow_json['status'] == "OK":
###                         #print("Shadow updated from client. Trying to sync again")
###                         #flash("Shadow updated from client. Trying to sync again...", 'info')
###                         previously_shadow_updated_from_client = True
###                         error_return =  items_send_post(client_text, recursive_count, previously_shadow_updated_from_client)
###                     else:
###                         error_return = "ERROR: unable to send_shadow"
###                 else:
###                     error_return = "ERROR: send_shadow response doesn't contain status"
###             except ValueError:
###                 error_return = r_send_shadow.text
###         elif r_json['error_type'] == "ServerShadowChecksumFailed":
###             #print("ServerShadowChecksumFailed")
###             # server sends its shadow:
###             if 'server_shadow' in r_json:
###                 new_client_shadow = r_json['server_shadow']
###                 #print("Shadow updated from server. Trying to sync again")
###                 #flash("Shadow updated from server. Trying to sync again...", 'error')
###                 error_return =  None
###             else:
###                 error_return = "ERROR: unable to update shadow from server"
###         else:
###             error_return = "ERROR<br />" + r_json['error_type']
###             if  'error_message' in r_json:
###                 error_return = error_return + "<br />" + r_json['error_message']
###                 error_return = error_return + "<br />" + "FULL MESSAGE:<br />" + json.dumps(r_json)
###     return error_return, new_client_shadow
###
###
### def __requests_post(url, payload):
###     return requests.post(
###       url,
###       headers={'Content-Type': 'application/json'},
###       data=json.dumps(payload)
###       )
###
###
### def __items_send_post(client_shadow_cksum, client_patches):
###     payload = {
###                'client_id': app.config['CLIENT_ID'],
###                'client_shadow_cksum': client_shadow_cksum,
###                'client_patches': client_patches,
###               }
###
###     url_for_send = app.config['API_URL'] + "/users/" + app.config['CLIENT_ID'] + "/items"
###     return __requests_post(url_for_send, payload)
###
###
### def __send_shadow_payload(item_id, item_shadow):
###     # FIXME use item_id not  client_id
###     payload = {
###                'client_id': app.config['CLIENT_ID'],
###                'client_shadow': item_shadow,
###               }
###
###     # FIXME SANITIZE THIS
###     url_for_shadow = app.config['API_URL'] + "/users/" + app.config['CLIENT_ID'] + "/items/" + item_id + "/shadow"
###     return __requests_post(url_for_shadow, payload)
###
###
### def items_send_get(node_id, item_id=None):
###     url_for_get = ""
###     if item_id:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items/" + item_id  # FIXME SANITIZE THIS
###     else:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items"  # FIXME SANITIZE THIS
###     return requests.get(
###       url_for_get,
###       headers={'Content-Type': 'application/json'}
###       )
###
###
### #
### # Sync "server" stuff
### #
### def items_receive_sync(user_id, node_id, request):
###     # FIXME this func is way to long
###     #import pdb; pdb.set_trace()
###     req = request.json
###     res = err_response('UnknownError', 'Uncontrolled error in server')
###     if req  in req and 'client_shadow_cksum' in req and 'client_patches' in req:
###
###         # FIXME: create atomicity
###         #
###         # steps 4 (atomic with 5, 6 & 7)
###         #
###         # The edits are applied to Server Text on a best-effort basis
###         # Server Text is updated with the result of the patch. Steps 4 and 5
###         # must be atomic, but they do not have to be blocking; they may be
###         # repeated until Server Text stays still long enough.
###         #
###         # Client Text and Server Shadow (or symmetrically Server Text and
###         # Client Shadow) must be absolutely identical after every half of the
###         # synchronization
###         #
###         # receive text_patches and client_shadow_cksum
###         #
###         # first check the server shadow cheksum
###         # if server_shadows[client_id] is empty ask for it
###
###         client_id = user_id
###         client_shadow_cksum = req['client_shadow_cksum']
###
###         server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###         server_shadow = db.get_shadow(client_id)
###         if server_shadow is None:
###             if server_text:
###                 # print("ServerShadowChecksumFailed")
###                  # FIXME: Change ServerShadowChecksumFailed to its own type
###                 res = {
###                     'status': 'ERROR',
###                     'error_type': 'ServerShadowChecksumFailed',
###                     'error_message': 'Shadows got desynced. Sending back the full server shadow',
###                     'server_shadow': server_text,
###                     }
###                 db.set_shadow(client_id, server_text)
###             else:
###                 # print("NoServerShadow")
###                 res = err_response('NoServerShadow',
###                 'No shadow found in the server. Send it again')
###             #print("NoServerShadow")
###             #res = err_response('NoServerShadow',
###             #'No shadow found in the server. Send it again')
###         else:
###             if not server_shadow: # FIXME coverage should show that it should never enter here
###                 server_shadow_cksum = 0
###             else:
###                 server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
###             # print("server_shadow_cksum {}".format(server_shadow_cksum))
###             #print(server_shadow)
###
###             if client_shadow_cksum != server_shadow_cksum:
###                 #FIXME what happenson first sync?
###                 #print("ServerShadowChecksumFailed")
###                 res = {
###                     'status': 'ERROR',
###                     'error_type': 'ServerShadowChecksumFailed',
###                     'error_message': 'Shadows got desynced. Sending back the full server shadow',
###                     'server_shadow' : server_shadow
###                     }
###             else:
###                 #print("shadows' checksums match")
###
###                 diff_obj = diff_match_patch.diff_match_patch()
###                 diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                 patches2 = diff_obj.patch_fromText(req['client_patches'])
###
###                 server_shadow_patch_results = None
###                 if not server_shadow:
###                     server_shadow_patch_results = diff_obj.patch_apply(
###                       patches2, "")
###                 else:
###                     server_shadow_patch_results = diff_obj.patch_apply(
###                       patches2, server_shadow)
###                 shadow_results = server_shadow_patch_results[1]
###
###                 # len(set(list)) should be 1 if all elements are the same
###                 if len(set(shadow_results)) == 1 and shadow_results[0]:
###                     # step 5
###                     db.set_shadow(client_id, server_shadow_patch_results[0])
###                     server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###
###
###                     server_text_patch_results = None
###                     server_text_patch_results = diff_obj.patch_apply(
###                           patches2, server_text)
###                     text_results = server_text_patch_results[1]
###
###                     if any(text_results):
###                         # step 7
###                         db.set_server_text(server_text_patch_results[0])
###
###                         #
###                         # Here starts second half of sync.
###                         #
###
###                         # print("""#
### # Here starts second half of sync.
### #""")
###
###                         diff_obj = diff_match_patch.diff_match_patch()
###                         diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                         # from https://neil.fraser.name/writing/sync/
###                         # step 1 & 2
###                         # Client Text is diffed against Shadow. This returns a list of edits which
###                         # have been performed on Client Text
###
###                         server_shadow = db.get_shadow(client_id)
###                         server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###                         edits = None
###                         if not server_shadow:
###                             edits = diff_obj.diff_main("", server_text)
###                         else:
###                             edits = diff_obj.diff_main(server_shadow, server_text)
###                         diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?
###
###                         patches = diff_obj.patch_make(edits)
###                         text_patches = diff_obj.patch_toText(patches)
###
###                         if not text_patches:
###                             # nothing to update!
###                             res = err_response('NoUpdate',
###                             'Nothing to update')
###                         else:
###                             #print("step 2 results: {}".format(text_patches))
###
###                             #step 3
###                             #
###                             # Client Text is copied over to Shadow. This copy must be identical to
###                             # the value of Client Text in step 1, so in a multi-threaded environment
###                             # a snapshot of the text should have been taken.
###                             server_shadow_cksum = 0
###                             if not server_shadow:
###                                 #print("server_shadow: None")
###                                 pass
###                             else:
###                                 server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
###                             #print("server_shadow_cksum {}".format(server_shadow_cksum))
###                             #print(server_shadow)
###
###                             db.set_shadow(client_id, server_text)
###
###                             res = {
###                                 'status': 'OK',
###                                 'client_id': client_id,
###                                 'server_shadow_cksum': server_shadow_cksum,
###                                 'text_patches': text_patches,
###                                 }
###                     else:
###                         # should I try to patch again?
###                         #print("FuzzyServerPatchFailed")
###                         res = {
###                             'status': 'ERROR',
###                             'error_type': 'FuzzyServerPatchFailed',
###                             'error_message': 'Fuzzy patching failled. Sending back the full server text',
###                             'server_text' : server_text
###                             }
###                 else:
###                     # FIXME: should I try to patch again?
###                     res = err_response('ServerPatchFailed',
###                     'Match-Patch failed in server')
###     else:
###         if not req:
###             log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
###             abort(415)
###         elif not 'client_id' in req or not 'client_shadow_cksum' in req or not 'client_patches' in req:
###             log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
###             abort(422)
###         else:
###             log.error("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###             abort(500)
###     log.debug("items_receive_sync - response: " + str(res))
###     return jsonify(**res)
###
###
### def err_response(error_type, error_message):
###     log.debug(error_type + " - " + error_message)
###     return {
###         'status': 'ERROR',
###         'error_type': error_type,
###         'error_message': error_message,
###         }
###
###
### def receive_shadow(user_id, node_id, item_id, request):
###     #import pdb; pdb.set_trace()
###     #print("receive_shadow")
###     req = request.json
###     res = None
###     if req and 'client_id' in req and 'client_shadow' in req:
###         res = err_response('UnknowErrorSendShadow',
###         'Unknown error in receive_shadow')
###
###         db.set_shadow(req['client_id'], req['client_shadow'])
###
###         # check if there is server content, as this can be the 1st sync
###         if not get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", item_id):
###             db.set_server_text(req['client_shadow'])
###
###         res = {
###             'status': 'OK',
###             }
###     else:
###         if not req:
###             log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
###             abort(415)
###         elif not 'client_id' in req or not 'client_shadow' in req:
###             log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
###             abort(422)
###         else:
###             log.error("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###             abort(500)
###     log.debug("receive_shadow - response: " + str(res))
###     return jsonify(**res)










### #
### # Sync stuff
### #
###
### def items_send_post(client_text, recursive_count, previously_shadow_updated_from_client=False):
###     """send a new client text to the server part"""
###     recursive_count += 1
###
###     if recursive_count > app.config['MAX_RECURSIVE_COUNT']:
###         return "MAX_RECURSIVE_COUNT"
###
###     client_shadow = db.get_shadow(app.config['CLIENT_ID'])
###
###     if not client_text:
###         # nothing to sync!
###         flash("nothing to sync...", 'warn')
###         return redirect(url_for('__main'), code=302)
###
###     diff_obj = diff_match_patch.diff_match_patch()
###     diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###     # from https://neil.fraser.name/writing/sync/
###     # step 1 & 2
###     # Client Text is diffed against Shadow. This returns a list of edits which
###     # have been performed on Client Text
###
###     edits = None
###     if not client_shadow:
###         edits = diff_obj.diff_main("", client_text)
###     else:
###         edits = diff_obj.diff_main(client_shadow, client_text)
###     diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?
###
###     patches = diff_obj.patch_make(edits)
###     text_patches = diff_obj.patch_toText(patches)
###
###     if not text_patches:
###         # nothing new to sync in this side. Check the other side for updates
###         if not previously_shadow_updated_from_client:
###             #flash("no changes", 'warn')
###             r = items_send_get("NODE_ID", "this_should_be_the_item_id")
###             try:
###                 r_json = r.json()
###                 if 'status' in r_json:
###                     if (r_json['status'] != "OK"
###                         and r_json['error_type'] != "NoUpdate"
###                         and r_json['error_type']  != "FuzzyServerPatchFailed"):
###                         pass
###                     fixme_text = """Continue with a function of "Here starts second half of sync" from below"""
###                     return(r.text + fixme_text)
###             except ValueError:
###                 #print("ValueError")
###                 return(r.text)
###         else:
###             flash("Sync OK!", 'info')
###         return redirect(url_for('__main'), code=302)
###     else:
###         # changes in this side that need to sync
###         # print("step 2 results: {}".format(text_patches))
###
###         try:
###             #step 3
###             #
###             # Client Text is copied over to Shadow. This copy must be identical to
###             # the value of Client Text in step 1, so in a multi-threaded environment
###             # a snapshot of the text should have been taken.
###
###             client_shadow_cksum = 0
###             if not client_shadow:
###                 # print("client_shadow: None")
###                 pass
###             else:
###                 #print("client_shadow: " + client_shadow)
###                 client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
###             #print("_____________pre__cksum_______")
###             #print(client_shadow_cksum)
###
###             client_shadow = client_text
###             db.set_content(app.config['CLIENT_ID'], client_text)
###             db.set_shadow(app.config['CLIENT_ID'], client_text)
###
###             # send text_patches, client_id and client_shadow_cksum
###             r = __items_send_post(client_shadow_cksum, text_patches)
###             try:
###                 r_json = r.json()
###                 if 'status' in r_json:
###                     if (r_json['status'] != "OK"
###                         and r_json['error_type'] != "NoUpdate"
###                         and r_json['error_type']  != "FuzzyServerPatchFailed"):
###                         # print("__manage_send_sync_error_return")
###                         error_return, new_client_shadow = __manage_send_sync_error_return(r_json, recursive_count)
###                         db.set_content(app.config['CLIENT_ID'], client_text)
###                         db.set_shadow(app.config['CLIENT_ID'], client_text)
###                         if new_client_shadow:
###                             db.set_shadow(app.config['CLIENT_ID'], new_client_shadow)
###                             #print("client shadow updated from the server")
###                             error_return = items_send_post(db.get_content(app.config['CLIENT_ID'], "FIXME"), recursive_count)
###                         return error_return
###                     else:
###                         db.set_content(app.config['CLIENT_ID'], client_text)
###                         db.set_shadow(app.config['CLIENT_ID'], client_text)
###                         if (r_json['status'] != "OK"
###                             and r_json['error_type'] == "NoUpdate"):
###                             # no changes so nothing else to do
###                             flash("Sync OK!", 'info')
###                             return redirect(url_for('__main'), code=302)
###                         elif (r_json['status'] != "OK"
###                             and r_json['error_type'] == "FuzzyServerPatchFailed"):
###                             if 'server_text' in r_json:
###                                 db.set_content(app.config['CLIENT_ID'], r_json['server_text'])
###                                 db.set_shadow(app.config['CLIENT_ID'], r_json['server_text'])
###                                 flash("Fuzzy patch failed. Data loss", 'error')
###                                 return redirect(url_for('__main'), code=302)
###                             else:
###                                 return "ERROR: malformed server response"
###                         else:
###                             if ('client_id' in r_json
###                                 and 'server_shadow_cksum' in r_json
###                                 and 'text_patches' in r_json
###                                 ):
###                                 #
###                                 # Here starts second half of sync.
###                                 #
###                                 # FIXME: create atomicity
###                                 #
###                                 # steps 4 (atomic with 5, 6 & 7)
###                                 #
###                                 # The edits are applied to Server Text on a best-effort basis
###                                 # Server Text is updated with the result of the patch. Steps 4 and 5
###                                 # must be atomic, but they do not have to be blocking; they may be
###                                 # repeated until Server Text stays still long enough.
###                                 #
###                                 # Client Text and Server Shadow (or symmetrically Server Text and
###                                 # Client Shadow) must be absolutely identical after every half of the
###                                 # synchronization
###                                 #
###                                 # receive text_patches and server_shadow_cksum
###                                 #
###                                 # first check the client shadow cheksum
###                                 #
###                                 client_shadow_cksum =  hashlib.md5(client_shadow.encode('utf-8')).hexdigest()
###                                 #print("client_shadow_cksum {}".format(client_shadow_cksum))
###
###                                 if client_shadow_cksum != r_json['server_shadow_cksum']:
###                                     return "ERROR: client shadow checksum failed"
###                                 else:
###                                     #print("shadows' checksums match")
###
###                                     diff_obj = diff_match_patch.diff_match_patch()
###                                     diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                                     patches = diff_obj.patch_fromText(r_json['text_patches'])
###
###                                     client_shadow_patch_results = None
###                                     client_shadow_patch_results = diff_obj.patch_apply(
###                                       patches, client_shadow)
###                                     shadow_results = client_shadow_patch_results[1]
###
###                                     # len(set(list)) should be 1 if all elements are the same
###                                     if len(set(shadow_results)) == 1 and shadow_results[0]:
###                                         # step 5
###                                         db.set_shadow(app.config['CLIENT_ID'], client_shadow_patch_results[0])
###                                         # should a break here be catastrophic ??
###                                         #
###                                         # step 6
###                                         client_text_patch_results = None
###                                         client_text_patch_results = diff_obj.patch_apply(
###                                               patches, client_text)
###                                         text_results = client_text_patch_results[1]
###
###                                         if any(text_results):
###                                             # step 7
###                                             db.set_content(app.config['CLIENT_ID'], client_text_patch_results[0])
###                                             #
###                                             # Here finishes the full sync.
###                                             #
###                                         flash("Sync OK!", 'info')
###                                         return redirect(url_for('__main'), code=302)
###                                     else:
###                                         # I should try to patch again
###                                         return "ERROR: Match-Patch failed in client"
###                             else:
###                                 return "ERROR: malformed server response"
###                 else:
###                     return "ERROR: send_sync response doesn't contain status"
###             except ValueError:
###                 #print("ValueError")
###                 return(r.text)
###         except ValueError:
###             #print("ValueError")
###             return "ERROR: ValueError" #FIXME
###         except requests.exceptions.ConnectionError:
###             #print("ConnectionError")
###             #return "ERROR: ConnectionError" #FIXME
###             flash("Server is unreachable", 'error')
###             return redirect(url_for('__main'), code=302)
###
###     # if we have got to here we have some coverage problems...
###     log.critical("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###     abort(500)
###
###
### def __manage_send_sync_error_return(r_json, recursive_count):
###     new_client_shadow = None
###
###     client_text = db.get_content(app.config['CLIENT_ID'], "FIXME")
###     if not client_text:
###         raise Exception('There should be a client_text by now...')
###
###     client_shadow = db.get_shadow(app.config['CLIENT_ID'])
###     if not client_shadow:
###         client_shadow = ""
###
###     error_return = "Unknown error in response"
###
###     if 'error_type' in r_json:
###         if r_json['error_type'] == "NoServerShadow":
###             #print("NoServerShadow")
###             # client sends its shadow:
###             r_send_shadow = __send_shadow_payload("this_should_be_the_item_id", client_shadow)
###             try:
###                 r_send_shadow_json = r_send_shadow.json()
###                 if 'status' in r_send_shadow_json:
###                     if r_send_shadow_json['status'] == "OK":
###                         #print("Shadow updated from client. Trying to sync again")
###                         #flash("Shadow updated from client. Trying to sync again...", 'info')
###                         previously_shadow_updated_from_client = True
###                         error_return =  items_send_post(client_text, recursive_count, previously_shadow_updated_from_client)
###                     else:
###                         error_return = "ERROR: unable to send_shadow"
###                 else:
###                     error_return = "ERROR: send_shadow response doesn't contain status"
###             except ValueError:
###                 error_return = r_send_shadow.text
###         elif r_json['error_type'] == "ServerShadowChecksumFailed":
###             #print("ServerShadowChecksumFailed")
###             # server sends its shadow:
###             if 'server_shadow' in r_json:
###                 new_client_shadow = r_json['server_shadow']
###                 #print("Shadow updated from server. Trying to sync again")
###                 #flash("Shadow updated from server. Trying to sync again...", 'error')
###                 error_return =  None
###             else:
###                 error_return = "ERROR: unable to update shadow from server"
###         else:
###             error_return = "ERROR<br />" + r_json['error_type']
###             if  'error_message' in r_json:
###                 error_return = error_return + "<br />" + r_json['error_message']
###                 error_return = error_return + "<br />" + "FULL MESSAGE:<br />" + json.dumps(r_json)
###     return error_return, new_client_shadow
###
###
### def __requests_post(url, payload):
###     return requests.post(
###       url,
###       headers={'Content-Type': 'application/json'},
###       data=json.dumps(payload)
###       )
###
###
### def __items_send_post(client_shadow_cksum, client_patches):
###     payload = {
###                'client_id': app.config['CLIENT_ID'],
###                'client_shadow_cksum': client_shadow_cksum,
###                'client_patches': client_patches,
###               }
###
###     url_for_send = app.config['API_URL'] + "/users/" + app.config['CLIENT_ID'] + "/items"
###     return __requests_post(url_for_send, payload)
###
###
### def __send_shadow_payload(item_id, item_shadow):
###     # FIXME use item_id not  client_id
###     payload = {
###                'client_id': app.config['CLIENT_ID'],
###                'client_shadow': item_shadow,
###               }
###
###     # FIXME SANITIZE THIS
###     url_for_shadow = app.config['API_URL'] + "/users/" + app.config['CLIENT_ID'] + "/items/" + item_id + "/shadow"
###     return __requests_post(url_for_shadow, payload)
###
###
### def items_send_get(node_id, item_id=None):
###     url_for_get = ""
###     if item_id:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items/" + item_id  # FIXME SANITIZE THIS
###     else:
###         url_for_get = app.config['API_URL'] + "/users/" + app.config['USER_ID'] + "/nodes/" + node_id + "/items"  # FIXME SANITIZE THIS
###     return requests.get(
###       url_for_get,
###       headers={'Content-Type': 'application/json'}
###       )
###
###
### #
### # Sync "server" stuff
### #
### def items_receive_sync(user_id, node_id, request):
###     # FIXME this func is way to long
###     #import pdb; pdb.set_trace()
###     req = request.json
###     res = err_response('UnknownError', 'Uncontrolled error in server')
###     if req  in req and 'client_shadow_cksum' in req and 'client_patches' in req:
###
###         # FIXME: create atomicity
###         #
###         # steps 4 (atomic with 5, 6 & 7)
###         #
###         # The edits are applied to Server Text on a best-effort basis
###         # Server Text is updated with the result of the patch. Steps 4 and 5
###         # must be atomic, but they do not have to be blocking; they may be
###         # repeated until Server Text stays still long enough.
###         #
###         # Client Text and Server Shadow (or symmetrically Server Text and
###         # Client Shadow) must be absolutely identical after every half of the
###         # synchronization
###         #
###         # receive text_patches and client_shadow_cksum
###         #
###         # first check the server shadow cheksum
###         # if server_shadows[client_id] is empty ask for it
###
###         client_id = user_id
###         client_shadow_cksum = req['client_shadow_cksum']
###
###         server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###         server_shadow = db.get_shadow(client_id)
###         if server_shadow is None:
###             if server_text:
###                 # print("ServerShadowChecksumFailed")
###                  # FIXME: Change ServerShadowChecksumFailed to its own type
###                 res = {
###                     'status': 'ERROR',
###                     'error_type': 'ServerShadowChecksumFailed',
###                     'error_message': 'Shadows got desynced. Sending back the full server shadow',
###                     'server_shadow': server_text,
###                     }
###                 db.set_shadow(client_id, server_text)
###             else:
###                 # print("NoServerShadow")
###                 res = err_response('NoServerShadow',
###                 'No shadow found in the server. Send it again')
###             #print("NoServerShadow")
###             #res = err_response('NoServerShadow',
###             #'No shadow found in the server. Send it again')
###         else:
###             if not server_shadow: # FIXME coverage should show that it should never enter here
###                 server_shadow_cksum = 0
###             else:
###                 server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
###             # print("server_shadow_cksum {}".format(server_shadow_cksum))
###             #print(server_shadow)
###
###             if client_shadow_cksum != server_shadow_cksum:
###                 #FIXME what happenson first sync?
###                 #print("ServerShadowChecksumFailed")
###                 res = {
###                     'status': 'ERROR',
###                     'error_type': 'ServerShadowChecksumFailed',
###                     'error_message': 'Shadows got desynced. Sending back the full server shadow',
###                     'server_shadow' : server_shadow
###                     }
###             else:
###                 #print("shadows' checksums match")
###
###                 diff_obj = diff_match_patch.diff_match_patch()
###                 diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                 patches2 = diff_obj.patch_fromText(req['client_patches'])
###
###                 server_shadow_patch_results = None
###                 if not server_shadow:
###                     server_shadow_patch_results = diff_obj.patch_apply(
###                       patches2, "")
###                 else:
###                     server_shadow_patch_results = diff_obj.patch_apply(
###                       patches2, server_shadow)
###                 shadow_results = server_shadow_patch_results[1]
###
###                 # len(set(list)) should be 1 if all elements are the same
###                 if len(set(shadow_results)) == 1 and shadow_results[0]:
###                     # step 5
###                     db.set_shadow(client_id, server_shadow_patch_results[0])
###                     server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###
###
###                     server_text_patch_results = None
###                     server_text_patch_results = diff_obj.patch_apply(
###                           patches2, server_text)
###                     text_results = server_text_patch_results[1]
###
###                     if any(text_results):
###                         # step 7
###                         db.set_server_text(server_text_patch_results[0])
###
###                         #
###                         # Here starts second half of sync.
###                         #
###
###                         # print("""#
### # Here starts second half of sync.
### #""")
###
###                         diff_obj = diff_match_patch.diff_match_patch()
###                         diff_obj.Diff_Timeout = app.config['DIFF_TIMEOUT']
###
###                         # from https://neil.fraser.name/writing/sync/
###                         # step 1 & 2
###                         # Client Text is diffed against Shadow. This returns a list of edits which
###                         # have been performed on Client Text
###
###                         server_shadow = db.get_shadow(client_id)
###                         server_text = get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", "this_should_be_the_item_id")
###                         edits = None
###                         if not server_shadow:
###                             edits = diff_obj.diff_main("", server_text)
###                         else:
###                             edits = diff_obj.diff_main(server_shadow, server_text)
###                         diff_obj.diff_cleanupSemantic(edits) # FIXME: optional?
###
###                         patches = diff_obj.patch_make(edits)
###                         text_patches = diff_obj.patch_toText(patches)
###
###                         if not text_patches:
###                             # nothing to update!
###                             res = err_response('NoUpdate',
###                             'Nothing to update')
###                         else:
###                             #print("step 2 results: {}".format(text_patches))
###
###                             #step 3
###                             #
###                             # Client Text is copied over to Shadow. This copy must be identical to
###                             # the value of Client Text in step 1, so in a multi-threaded environment
###                             # a snapshot of the text should have been taken.
###                             server_shadow_cksum = 0
###                             if not server_shadow:
###                                 #print("server_shadow: None")
###                                 pass
###                             else:
###                                 server_shadow_cksum = hashlib.md5(server_shadow.encode('utf-8')).hexdigest()
###                             #print("server_shadow_cksum {}".format(server_shadow_cksum))
###                             #print(server_shadow)
###
###                             db.set_shadow(client_id, server_text)
###
###                             res = {
###                                 'status': 'OK',
###                                 'client_id': client_id,
###                                 'server_shadow_cksum': server_shadow_cksum,
###                                 'text_patches': text_patches,
###                                 }
###                     else:
###                         # should I try to patch again?
###                         #print("FuzzyServerPatchFailed")
###                         res = {
###                             'status': 'ERROR',
###                             'error_type': 'FuzzyServerPatchFailed',
###                             'error_message': 'Fuzzy patching failled. Sending back the full server text',
###                             'server_text' : server_text
###                             }
###                 else:
###                     # FIXME: should I try to patch again?
###                     res = err_response('ServerPatchFailed',
###                     'Match-Patch failed in server')
###     else:
###         if not req:
###             log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
###             abort(415)
###         elif not 'client_id' in req or not 'client_shadow_cksum' in req or not 'client_patches' in req:
###             log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
###             abort(422)
###         else:
###             log.error("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###             abort(500)
###     log.debug("items_receive_sync - response: " + str(res))
###     return jsonify(**res)
###
###
### def err_response(error_type, error_message):
###     log.debug(error_type + " - " + error_message)
###     return {
###         'status': 'ERROR',
###         'error_type': error_type,
###         'error_message': error_message,
###         }
###
###
### def receive_shadow(user_id, node_id, item_id, request):
###     #import pdb; pdb.set_trace()
###     #print("receive_shadow")
###     req = request.json
###     res = None
###     if req and 'client_id' in req and 'client_shadow' in req:
###         res = err_response('UnknowErrorSendShadow',
###         'Unknown error in receive_shadow')
###
###         db.set_shadow(req['client_id'], req['client_shadow'])
###
###         # check if there is server content, as this can be the 1st sync
###         if not get_user_node_item_by_id(user_id, "this_should_be_the_nod_id", item_id):
###             db.set_server_text(req['client_shadow'])
###
###         res = {
###             'status': 'OK',
###             }
###     else:
###         if not req:
###             log.warning("HTTP 415 - Unsupported Media Type: No payload found in the request")
###             abort(415)
###         elif not 'client_id' in req or not 'client_shadow' in req:
###             log.warning("HTTP 422 - Unprocessable Entity: No content found in the request")
###             abort(422)
###         else:
###             log.error("HTTP 500 " + sys._getframe().f_code.co_name + " :: " + sys._getframe().f_code.co_filename + ":" + str(sys._getframe().f_lineno))
###             abort(500)
###     log.debug("receive_shadow - response: " + str(res))
###     return jsonify(**res)
