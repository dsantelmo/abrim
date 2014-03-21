#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys, errno, os

def read_text(name, file_path, verbosity=0):
    file_path = os.path.abspath(file_path)
    try:
        with open(file_path, 'r+') as f:
            if verbosity >= 2:
                print("Reading %s" % file_path)
            return file_path, f.read()
    except IOError as ioerr:
        print('ERROR: error reading file', file=sys.stderr)
        return None, None

def read_stdin(name, stdin, verbosity=0):
    if stdin and name:
        try:
            if verbosity >= 2:
                print("Reading stdin")
            return os.path.abspath(name), stdin.read()
        except IOError as ioerr:
            print('ERROR: error reading stdin', file=sys.stderr)
            return None, None
    else:
        print('ERROR: no filename specified with --name', file=sys.stderr)
        return None, None

def write_text(text, file_path, name, stdin=None, verbosity=0):
    if file_path == '-':
        if stdin and name:
            try:
                #stdout output
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
                print("open file %s" % file_path)
                print("wrote text: %s" % text)
                f.write(text)
                return True
        except IOError as ioerr:
            print('ERROR: error writing file', file=sys.stderr)
            return False

if __name__ == "__main__":
    pass

