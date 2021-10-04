#!/bin/sh

set -e

rm -rf dist
python setup.py bdist_wheel
twine upload dist/*.whl