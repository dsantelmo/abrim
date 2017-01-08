#!/bin/sh

python test/db_tests.py -b
python test/node_tests.py -b
python test/sync_tests.py -b
