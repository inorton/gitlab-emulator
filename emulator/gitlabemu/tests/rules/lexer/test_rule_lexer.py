from typing import List

import pytest
from ....rules.lexer import Parser
from .cases import JOINED_EXPRESSIONS, PARENS_EXPRESSIONS


@pytest.mark.parametrize(
    "exp, expected", [
        pytest.param(exp, expected, id=exp) for exp, expected in JOINED_EXPRESSIONS.items()
    ]
)
def test_simple_tokenization(exp: str, expected: List[str]):
    parser = Parser()
    actual = parser.parse(exp)
    strings = [str(x) for x in actual]
    assert strings == expected


@pytest.mark.parametrize(
    "exp, expected", [
        pytest.param(exp, expected, id=exp) for exp, expected in PARENS_EXPRESSIONS.items()
    ]
)
def test_grouped_tokenization(exp: str, expected: List[str]):
    parser = Parser()
    actual = parser.parse(exp)
    strings = [str(x) for x in actual]
    assert strings == expected




