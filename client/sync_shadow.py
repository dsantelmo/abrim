#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys, errno, os
import hashlib

appname="AbrimSync"
appauthor="Abrim"
try:
    import appdirs
    temp_path = appdirs.user_data_dir(appname, appauthor)
except ImportError:
    try:
        temp_path = os.path.join("." + program_name, temp_path_name)
    except AttributeError:
        temp_path='.abrim/temp_path_name'
if not os.path.exists(temp_path):
    os.makedirs(temp_path)

def __get_shadow_path(file_path, verbosity=0):
    shadow_prefix="."
    shadow_suffix=".shadow"
    #FIXME file name too long?
    file_path = os.path.abspath(file_path)
    shadow_name=shadow_prefix + hashlib.sha256(file_path).hexdigest() + shadow_suffix 
    if verbosity >= 2:
        print("Path: %s" % (file_path,))
        print("Shadow: %s" % (shadow_name,))
    return os.path.join(temp_path, shadow_name)

class ShadowCreationError(Exception):
    def __init__(self, message):
        self.message = message
        print(message, file=sys.stderr)
        exit(errno.EIO)
        
    def __str__(self):
        return repr(self.message)

def __create_shadow(text, shadow_path, verbosity=0):
    if verbosity >= 2:
        print("No shadow found. Creating a new one at %s" % shadow_path)
    try:
        with open(shadow_path,'w') as f:
            f.write(text)
            f.flush()
    except IOError as ioerr:
        raise ShadowCreationError("Unable to write to %s" % shadow_path)

def __create_if_not_exists_shadow(text, shadow_path, verbosity=0):
    try:
        with open(shadow_path,'r+') as f:
            shadow=f.read()
            if not shadow:
                __create_shadow(text, shadow_path)
    except IOError as ioerr:
        __create_shadow(text, shadow_path, verbosity)
        with open(shadow_path,'r+') as f:
            shadow=f.read()
            if not shadow:
                raise ShadowCreationError("Unable to read %s" % shadow_path)
    if verbosity >= 2:
        print("Shadow found at %s" % shadow_path)

def read_shadow(text, file_path, verbosity=0):
    shadow_path=__get_shadow_path(file_path, verbosity)
    __create_if_not_exists_shadow(text, shadow_path, verbosity)
    try:
        with open(shadow_path,'r+') as f:
            return f.read()
    except IOError as ioerr:
        return None

def write_shadow(text, file_path, verbosity=0):
    shadow_path=__get_shadow_path(file_path, verbosity)
    __create_if_not_exists_shadow(text, shadow_path, verbosity)
    try:
        with open(shadow_path,'w') as f:
            f.write(text)
            f.flush()
            if verbosity >= 2:
                print("Shadow wrote to %s" % shadow_path)
    except IOError as ioerr:
        raise ShadowCreationError("Unable to write %s" % shadow_path)


if __name__ == "__main__":
    pass
