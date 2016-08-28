#!/usr/bin/env python

def secure_filename(filename):
    filename.lower()
    filename = filename.replace(':','-')
    filename = filename.replace(' ','_')
    keep_chars = ('_','_','.',)
    "".join(c for c in filename if c.isalnum() or c in keep_chars).strip()
    return filename
