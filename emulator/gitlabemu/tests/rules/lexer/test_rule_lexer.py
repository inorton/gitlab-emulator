from ....rules import parser


def test_simple():
    result = parser.evaluate_rule('$COLOR == "red"', {"COLOR": "red"})
    assert result is True

    result = parser.evaluate_rule('$COLOR == "red"', {"COLOR": "Red"})
    assert result is False

    result = parser.evaluate_rule('"red" == "red"', {"COLOR": "Red"})
    assert result is True

    result = parser.evaluate_rule('"blue" == $COLOR', {"COLOR": "blue"})
    assert result is True

def test_variable_defined():
    result = parser.evaluate_rule('$COLOR', {})
    assert result is False

    result = parser.evaluate_rule('$COLOR', {"COLOR": ""})
    assert result is False

    result = parser.evaluate_rule('$COLOR', {"COLOR": "blue"})
    assert result is True


def test_boolean():
    result = parser.evaluate_rule(
        '$DEFINED && $SIZE == "small"',
        {
            "DEFINED": "1",
            "SIZE": "small",
        })
    assert result

    result = parser.evaluate_rule(
        '$DEFINED && $SIZE == "small"',
        {
            "SIZE": "small",
        })
    assert result is False

    result = parser.evaluate_rule(
        '$DEFINED && $SIZE == "small"',
        {
            "DEFINED": "",
            "SIZE": "small",
        })
    assert result is False

    result = parser.evaluate_rule(
        '$DEFINED && $SIZE == "small"',
        {
            "DEFINED": "yes",
            "SIZE": "big",
        })
    assert result is False

    result = parser.evaluate_rule(
        '$DEFINED || $SIZE == "small"',
        {
            "SIZE": "small"
        })
    assert result is True

    result = parser.evaluate_rule(
        '$DEFINED || $SIZE == "small"',
        {
            "DEFINED": "1"
        })
    assert result is True

    result = parser.evaluate_rule(
        '$DEFINED || $SIZE == "small"',
        {
            "SHAPE": "square"
        })
    assert result is False
