#!/bin/sh

set -e

rm -rf dist
python3 -m build
twine upload dist/*.whl