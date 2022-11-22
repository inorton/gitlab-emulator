#!/bin/sh
#
# Run this if you alter the g4 file
#
set -e
antlr4 -visitor -no-listener -Dlanguage=Python3 GitlabRule.g4