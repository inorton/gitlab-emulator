#!/bin/sh

set -e

rm -rf dist
python3 setup.py bdist_wheel
python3 -m twine upload dist/*.whl
