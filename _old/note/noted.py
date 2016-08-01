#!/usr/bin/env python
# -*- coding: utf-8 -*-

import note
from flask import Flask, redirect, url_for
app = Flask(__name__)

@app.route('/')
def __root():
    return redirect(url_for('__list'))

@app.route('/list/')
def __list_notes():
    return note.list_notes()

@app.route('/last/<int:changes_num>')
def __last(changes_num):
    return note.last(changes_num)

@app.route('/changes_before_id/<ch_id>')
def __changes_since_id(ch_id):
    return redirect(url_for('__changes_before_id_num',
                            change_id=ch_id,
                            num=0))

@app.route('/changes_before_id/<change_id>/<int:num>')
def __changes_before_id_num(change_id, num=0):
    return note.changes_before_id(change_id, num)

@app.route('/changes_since_id/<ch_id>')
def __changes_since_id(ch_id):
    return redirect(url_for('__changes_since_id_num',
                            change_id=ch_id,
                            num=0))

@app.route('/changes_since_id/<change_id>/<int:num>')
def __changes_since_id_num(change_id, num=0):
    return note.changes_since_id(change_id, num)

@app.route('/summ_changes_since_id/<change_id>')
def __summ_changes_since_id(change_id):
    return note.summ_changes_since_id(change_id)

@app.route('/get_change_by_id/<change_id>')
def __get_change_by_id(change_id):
    return note.get_change_by_id(change_id)

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
