#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse, sys, errno, os
import hashlib
import tempfile
import diff_match_patch
import requests
import json

from sync_shadow import read_shadow, write_shadow

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

def __read_text(file_path, name, stdin=None):
    if file_path == '-':
        if stdin and name:
            try:
                return os.path.abspath(name), stdin.read()
            except IOError as ioerr:
                print('ERROR: error reading stdin', file=sys.stderr)
                return None, None
        else:
            print('ERROR: no filename specified with --name', file=sys.stderr)
            return None, None
    else:
        file_path = os.path.abspath(file_path)
        try:
            with open(file_path, 'r+') as f:
                return file_path, f.read()
        except IOError as ioerr:
            print('ERROR: error reading file', file=sys.stderr)
            return None, None


def __write_text(text, file_path, name, stdin=None):
    if file_path == '-':
        if stdin and name:
            try:
                print(text)
                return True
            except IOError as ioerr:
                print('ERROR: error reading stdin', file=sys.stderr)
                return False
        else:
            print('ERROR: no filename specified with --name', file=sys.stderr)
            return False
    else:
        file_path = os.path.abspath(file_path)
        try:
            with open(file_path, 'w') as f:
                f.write(text)
                return True
        except IOError as ioerr:
            print('ERROR: error reading file', file=sys.stderr)
            return False

def __diff(shadow, text):
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    return differ.diff_main(shadow, text)

def __patch(text,diff):
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    return differ.patch_toText(differ.patch_make(text,diff))

def __send_to_server(server, file_path, patch):
    payload = {'doc': file_path, 'patch': patch,}
    r = requests.post(server, data=payload)
    if r.status_code == 200:
        ret=json.loads(r.text)
        ret_doc=ret['doc']
        ret_patch=ret['patch']
        if (ret_doc == file_path and 
          ret_patch != 'no patch' and 
          ret_patch != "patch failed" ):
            return ret_patch
    return None

def sync(server, file_path, text, shadow, verbosity=0):
    file_path = os.path.abspath(file_path)
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
            print("###########")
            print(patch)
            print("###########")

    write_shadow(text, file_path, verbosity)

    if verbosity >= 1:
        print("Connecting to %s" % server)

    patch2=__send_to_server(server, file_path, patch)
    differ=diff_match_patch.diff_match_patch()
    differ.Diff_Timeout=3
    patch3=differ.patch_fromText(patch2)
    print(patch3)
    resul=differ.patch_apply(patch3,text)
    print(resul)
    if resul[1]:
        return resul[0]
    return None

if __name__ == "__main__":
    args = parse_args()

    filename, text=__read_text(args.file, args.name, sys.stdin)
    if not (filename or text):
        exit(errno.EIO)

    shadow=read_shadow(text, filename, args.verbosity)
    if not shadow:
        print('ERROR: error reading shadow file', file=sys.stderr)
        exit(errno.EIO)

    if text and shadow:
        server="http://127.0.0.1:5000/"
        resul=sync(server, filename, text, shadow, args.verbosity)
        if resul:
            write_ok=__write_text(resul, filename, args.name, sys.stdin)
            print(write_ok)
