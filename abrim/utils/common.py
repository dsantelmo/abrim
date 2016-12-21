#!/usr/bin/env python
import random
import string
import sys

def secure_filename(filename):
    filename.lower()
    filename = filename.replace(':','-')
    filename = filename.replace(' ','_')
    keep_chars = ('_','_','.',)
    "".join(c for c in filename if c.isalnum() or c in keep_chars).strip()
    return filename

def generate_random_id(id_length):
    return ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(id_length))