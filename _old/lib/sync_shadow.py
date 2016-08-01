#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import errno
import os
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

def __get_shadow_path(file_path, server=False, verbosity=0):
    shadow_prefix="."
    shadow_suffix=".shadow"
    #FIXME file name too long?
    file_path = os.path.abspath(file_path)
    if server:
        file_path="server://"+file_path
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

def __create_shadow(shadow_path, text, verbosity=0):
    if text is None:
        text=""
        if verbosity >= 2:
            print("No shadow found. Creating a new EMPTY one at %s" % shadow_path)
    else:
        if verbosity >= 2:
            print("No shadow found. Creating a new one at %s" % shadow_path)

    try:
        with open(shadow_path,'w') as f:
            f.write(text)
            f.flush()
    except IOError as ioerr:
        raise ShadowCreationError("Unable to write to %s" % shadow_path)

# secuencia de shadows numerados aleatorio, si no hay ninguno pedirlo al servidor
# almacenar todo menos los textos en sqlite y dejarse de paths e historias
def __create_if_not_exists_shadow(shadow_path, text, verbosity=0):
    try:
        with open(shadow_path,'r+') as f:
            shadow=f.read()
            if not shadow:
                __create_shadow(shadow_path, text)
            else:
                return shadow
    except IOError as ioerr:
        __create_shadow(shadow_path, text, verbosity)
        with open(shadow_path,'r+') as f:
            shadow=f.read()
            if not shadow:
                raise ShadowCreationError("Unable to read %s" % shadow_path)
    if verbosity >= 2:
        print("Shadow found at %s" % shadow_path)

def read_shadow(file_path, text=None, server=False, verbosity=0):
    shadow_path=__get_shadow_path(file_path, server, verbosity)
    __create_if_not_exists_shadow(shadow_path, text, verbosity)
    try:
        with open(shadow_path,'r+') as f:
            return f.read()
    except IOError as ioerr:
        return None

def write_shadow(file_path, text, server=False, verbosity=0):
    shadow_path=__get_shadow_path(file_path, server, verbosity)
    __create_if_not_exists_shadow(shadow_path, text, verbosity)
    try:
        with open(shadow_path,'w') as f:
            f.write(text)
            f.flush()
            if verbosity >= 2:
                print("Shadow wrote to %s" % shadow_path)
    except IOError as ioerr:
        raise ShadowCreationError("Unable to write %s" % shadow_path)

class SyncShadow:
    """Class to manage shadow text operations"""

    def __init__(self, file_path, server, verbosity=0):
        self.file_path = file_path
        self.server = server
        self.verbosity = verbosity
        self.shadow_path = None
        self.text = None
        #controlar que no mandan None en las primeras variables

    def set_text(self, text):
        self.text = text

    def __get_shadow_path(self):
        shadow_prefix="."
        shadow_suffix=".shadow"
        #FIXME file name too long?
        file_path = os.path.abspath(self.file_path)
        if self.server:
            file_path="server://"+file_path
        shadow_name=shadow_prefix + hashlib.sha256(file_path).hexdigest() + shadow_suffix 
        if self.verbosity >= 2:
            print("Path: %s" % (file_path,))
            print("Shadow: %s" % (shadow_name,))
        return os.path.join(temp_path, shadow_name)

    def read_shadow(self):
        if not self.shadow_path:
            self.shadow_path = self.__get_shadow_path()
        try:
            with open(self.shadow_path,'r+') as f:
                self.text = f.read()
        except IOError as ioerr:
            return None


if __name__ == "__main__":
    pass
