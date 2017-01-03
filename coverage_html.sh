#!/bin/sh

# open_browser is an alias
coverage run --branch test/node_tests.py && coverage html && open_browser htmlcov/index.html
