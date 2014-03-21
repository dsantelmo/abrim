#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import sys
import errno
import os
import hashlib
import tempfile
import diff_match_patch
import requests
import json

os.sys.path.insert(0, os.path.join(os.getcwd(), "../lib/")) 
from sync_shadow import read_shadow, write_shadow, SyncShadow
import sync_text 


appname = "AbrimSync"
appauthor = "Abrim"
version="0.1.0"
version_text="(%s version %s)" % (appname, version,)

def parse_args():
    parser = argparse.ArgumentParser() #(appname)
    parser.add_argument('-V', '--version', action='version', 
      version="%(prog)s "+version_text )
    parser.add_argument("-v", "--verbosity", action="count", 
      default=0, help="increase output verbosity")
    parser.add_argument('action', choices=('add', 'update', 'delete'), 
      help="action for the file")
    parser.add_argument('file', help='file to sync. Use \'-\' for stdin')
    parser.add_argument('--name',
      help='file to sync if using stdin. Ignored otherwise')
    return parser.parse_args()

def __diff(shadow, text):
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    return differ.diff_main(shadow, text)

def __patch(text, diff):
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    return differ.patch_toText(differ.patch_make(text,diff))

def __send_to_server(server, file_path, patch, verbosity=0):
    payload = {'doc': file_path, 'patch': patch,}
    if verbosity >= 1:
        print("Seding payload to server %s" % server)
    if verbosity >= 3:
        print("###payload######")
        print(payload)
        print("###endpayload###")
    r = requests.post(server, data=payload)
    if r.status_code == 200:
        rep=json.loads(r.text)
        if verbosity >= 1:
            print("Response from server %s" % server)
        if verbosity >= 3:
            print("###reply######")
            print(rep)
            print("###endreply###")
        rep_doc=rep['doc']
        rep_patch=rep['patch']
        if (rep_doc == file_path and 
          rep_patch != 'no patch' and 
          rep_patch != "patch failed" ):
            return rep_patch
    else:
        if verbosity >= 1:
            print("Response but no patch from server %s" % server)

    return None

def sync(server, file_path, text, shadow, verbosity=0):
    file_path = os.path.abspath(file_path)
    if verbosity >= 3:
        print("###text######")
        print(text)
        print("###endtext###")
        print("###shadow######")
        print(shadow)
        print("###endshadow###")
    diff=__diff(text, shadow)
    patch=__patch(shadow, diff)
    if not patch:
        if verbosity >= 1:
             print("Nothing to sync")
        return None
    else:
        if verbosity >= 1:
            print("Synchronizing %s" % file_path)
        if verbosity >= 3:
            print("###patch######")
            print(patch)
            print("###endpatch###")

    write_shadow(file_path, text, False, verbosity)

    if verbosity >= 1:
        print("Connecting to %s" % server)

    reply_patch=__send_to_server(server, file_path, patch, verbosity)
    if verbosity >= 1:
        if reply_patch:
            print("Response from server with a patch")
        else:
            print("Response from server, but no patch")

    if verbosity >= 3:
        print("###reply_patch######")
        print(reply_patch)
        print("###endreply_patch###")
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    patch3=differ.patch_fromText(reply_patch)
    resul=differ.patch_apply(patch3,text)
    if resul[1]:
        if verbosity >= 3:
            print("###local_changes######")
            print(resul[0])
            print("###endlocal_changes###")
        return resul[0]
    else:
        if verbosity >= 3:
            print("Unable to create local changes")
        return None

if __name__ == "__main__":
    args = parse_args()

    if args.file == "-":
        filename, text=sync_text.read_stdin(args.name, sys.stdin, args.verbosity)
    else:
        filename, text=sync_text.read_text(args.name, args.file, args.verbosity)

    if not (filename or text):
        exit(errno.EIO)

    #shadow=read_shadow(filename, text, False, args.verbosity)
    shad=SyncShadow(filename, None, args.verbosity)
    shad.read_shadow()
    if not shad.text:
        print("No shadow file")
        #print('ERROR: error reading shadow file', file=sys.stderr)
        #exit(errno.EIO)
        shad.text = ""
    shadow = shad.text
    if text:
        server="http://127.0.0.1:5000/"
        resul=sync(server, filename, text, shadow, args.verbosity)
        if resul:
            if args.file != "-":
                if args.verbosity >= 2:
                    print("Writing changes to local file")
                write_ok=sync_text.write_text(resul, filename, args.name, sys.stdin, args.verbosity)
            else:
                print(resul)
        else:
            print("No results")

    if 1 == 2:
        print('ERROR: error reading shadow file', file=sys.stderr)
        exit(errno.EIO)

