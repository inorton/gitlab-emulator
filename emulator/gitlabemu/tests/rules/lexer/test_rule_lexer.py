from typing import List

import pytest
from ....rules import parser


def test_simple():
    variables = {
        "COLOR": "red"
    }
    result = parser.evaluate_rule('$COLOR == "red"', variables)
    result = parser.evaluate_rule('($COLOR) && $FOO == "bar"', variables)
