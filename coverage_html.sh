#!/bin/sh

# open_browser is an alias
source ~/.bash_aliases
coverage run --branch test/node_tests.py && coverage html && open_browser htmlcov/index.html
