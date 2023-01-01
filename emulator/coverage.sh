#!/bin/sh
RV=1
python -m pytest --cov gitlabemu --junitxml=test-results.xml -vv --cov-report=xml:pytest-coverage.xml "$@" && RV=0
python -m coverage html -d coverage_html --title "GLE coverage"
exit $RV