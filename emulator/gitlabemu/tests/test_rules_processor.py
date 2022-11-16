import pytest
from ..rules import syntax, lexer
from ..rules.lexer import Token
from ..rules.syntax import TreeNode


@pytest.mark.parametrize(["left", "op", "right"],
                         [
                             pytest.param('$COLOR', '==', '"red"', id='$COLOR == "red"'),
                             pytest.param('$SIZE', '!=', '"small"', id='$SIZE != "small"'),
                             pytest.param('$SHAPE', '=~', '/angle$/', id='$SHAPE =~ /angle$/'),
                             pytest.param('$NAME', '!~', '/rover/', id='$NAME !~ /rover/'),
                         ])
def test_syntax_parse_simple_cmp(left: str, op: str, right: str):
    """Test we can parse a single comparison"""
    lex = lexer.Parser()
    text = f"{left} {op} {right}"
    tokens = lex.parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.parse_one()
    assert result, "failed to get a syntax node"
    assert not rule.tokens, "unexpected tokens remaining"
    assert result.op == op
    assert result.left.value == left
    assert result.right.value == right

def test_syntax_parse_simple_defined():
    """Test we can parse a single defined var"""
    lex = lexer.Parser()
    text = '$COLOR'
    tokens = lex.parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.parse_one()
    assert result, "failed to get a syntax node"
    assert not rule.tokens, "unexpected tokens remaining"
    assert result.op == "defined"
    assert result.left.value == '$COLOR'
    assert not result.right


def test_parse_boolean_defined_expr():
    lex = lexer.Parser()
    text = '$COLOR && $SHAPE'
    tokens = lex.parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.parse_one()
    assert result
    assert result.op == "defined"
    assert result.left.value == "$COLOR"
    assert not result.right
    assert len(rule.tokens) > 0

    result = rule.parse_one()
    assert result.op == "&&"
    assert result.left
    assert result.left.op == "defined"
    assert result.left.left.value == "$COLOR"
    assert not result.left.right
    assert not result.right
    assert len(rule.tokens) > 0

    result = rule.parse_one()
    assert result
    assert result.op == "defined"
    assert result.left.value == "$SHAPE"
    assert not len(rule.tokens)  # all tokens consumed

    root = rule.root
    assert root.op == "&&"
    assert root.left
    assert root.left.op == "defined"
    assert root.left.left.value == "$COLOR"
    assert root.right
    assert root.right.op == "defined"
    assert root.right.left.value == "$SHAPE"


def test_parse_boolean_cmp_expr():
    lex = lexer.Parser()
    text = '$NAME == "fred" || $NAME == "joan"'
    tokens = lex.parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.parse_one()
    assert result.op == "=="
    assert result.left.value == "$NAME"
    assert result.right.value == '"fred"'
    assert rule.tokens

    result = rule.parse_one()
    assert result.op == "||"
    assert result.left.op == "=="
    assert result.left.left.value == "$NAME"
    assert result.left.right.value == '"fred"'
    assert not result.right
    assert result.left.parent == result

    result = rule.parse_one()
    assert not rule.tokens
    assert result.op == "=="
    assert result.left.value == "$NAME"
    assert result.right.value == '"joan"'
    root = rule.root
    assert root != result
    assert result.parent == root
    assert root.left
    assert root.right
    assert root.right == result


def test_parse_boolean_braces():
    lex = lexer.Parser()
    text = '($NAME == "fred") || $CLASS'
    tokens = lex.parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.parse_one()
    assert result.op is "("
    assert result.left is None
    assert result.right is None
    assert rule.tokens
    result = rule.parse_one()
    assert result.op == "=="
    assert isinstance(result.left, Token)
    assert result.left.value == "$NAME"
    assert isinstance(result.right, Token)
    assert result.right.value == '"fred"'
    assert rule.tokens

    result = rule.parse_one()
    assert result.op == ")"

    result = rule.parse_one()
    assert result.op == "||"
    assert isinstance(result.left, TreeNode)
    assert result.left.left.value == "$NAME"
    assert result.left.right.value == '"fred"'
    assert rule.tokens

    result = rule.parse_one()
    assert result.op == "defined"
    assert isinstance(result.left, Token)
    assert result.left.value == "$CLASS"

    assert not rule.tokens
    assert rule.root.op == "||"


def test_parse_full_complex():
    text = '($BUILD_TYPE == "release" || ($BUILD_TYPE == "hotfix")) && $PLATFORM == "Linux"'
    tokens = lexer.Parser().parse(text)
    rule = syntax.Rule(text, tokens)
    rule.parse()
    assert rule.root.op == "&&"


def test_simple_eval_defined():
    text = "$FOO"
    tokens = lexer.Parser().parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.evaluate({"FOO": "red"})
    assert result

    result = rule.evaluate({"BAR": "red"})
    assert not result


def test_simple_eval_cmp():
    text = '$COLOR == "blue"'
    tokens = lexer.Parser().parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.evaluate({"FOO": "red"})
    assert not result

    result = rule.evaluate({"COLOR": "red"})
    assert not result

    result = rule.evaluate({"COLOR": "blue"})
    assert result


def test_logical_eval():
    text = '$COLOR == "blue" || $COLOR == "red"'
    tokens = lexer.Parser().parse(text)
    rule = syntax.Rule(text, tokens)
    result = rule.evaluate({})
    assert not result

    result = rule.evaluate({"COLOR": "green"})
    assert not result

    result = rule.evaluate({"COLOR": "red"})
    assert result

    result = rule.evaluate({"COLOR": "blue"})
    assert result


def test_complex_logical_full_eval():
    text = '$COLOR == "blue" && ($SIZE =~ /small/ || $SIZE =~ /very/) && $SHAPE'
    tokens = lexer.Parser().parse(text)
    rule = syntax.Rule(text, tokens)
    rule.parse()
    assert not rule.tokens
    assert rule.root

    result = rule.evaluate({
        "COLOR": "blue",
        "SIZE": "very-large",
        "SHAPE": "cube"
    })
    assert result

    result = rule.evaluate({
        "COLOR": "green",
        "SIZE": "very-large",
        "SHAPE": "cube"
    })
    assert not result

