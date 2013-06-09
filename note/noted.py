#!/usr/bin/env python
# -*- coding: utf-8 -*-

import note
from flask import Flask, redirect, url_for
app = Flask(__name__)

@app.route('/')
def __root():
    return note.redirect(url_for('__list'))

@app.route('/list/')
def __list():
    return note.list()

@app.route('/last/<int:changes_num>')
def __last(changes_num):
    return note.last(changes_num)

@app.route('/changes_since_id/<change_id>')
def __changes_since_id(change_id):
    return note.changes_since_id(change_id)

@app.route('/summ_changes_since_id/<change_id>')
def __summ_changes_since_id(change_id):
    return note.summ_changes_since_id(change_id)

@app.route('/get_change_by_id/<change_id>')
def __get_change_by_id(change_id):
    return note.get_change_by_id(change_id)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
