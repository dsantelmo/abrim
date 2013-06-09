#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
from note import *
from flask import Flask, redirect, url_for
app = Flask(__name__)

@app.route('/')
def __root():
    return redirect(url_for('__list'))

@app.route('/list/')
def __list():
    return list()

@app.route('/last/<int:changes_num>')
def __last(changes_num):
    return last(changes_num)

@app.route('/changes_since_id/<change_id>')
def __changes_since_id(change_id):
    return changes_since_id(change_id)

@app.route('/summ_changes_since_id/<change_id>')
def __summ_changes_since_id(change_id):
    return summ_changes_since_id(change_id)

@app.route('/get_change_by_id/<change_id>')
def __get_change_by_id(change_id):
    return get_change_by_id(change_id)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
