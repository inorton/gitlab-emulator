from typing import List

import pytest
from ....rules.lexer import Parser, Token
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


def test_unterminated_quotes():
    parser = Parser()
    for q in '\'"/':
        with pytest.raises(SyntaxError):
            parser.parse(f"{q}FOO")

def test_parser_repr():
    parser = Parser()
    tokens = parser.parse("")
    assert not tokens
    repr_text = repr(parser)
    assert "Parser, remaining: []" == repr_text


def test_parser_token_repr():
    token = Token()
    token.value = "$VAR"
    assert token.__repr__() == "Token [$VAR] (incomplete)"
    token.complete = True
    assert token.__repr__() == "Token [$VAR]"


def test_parser_token_error():
    with pytest.raises(ValueError):
        token = Token()
        x = token.first

