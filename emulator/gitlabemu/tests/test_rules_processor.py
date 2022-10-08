from ..rules import evaluate_expression


def test_evaluate_expression():
    variables = {
        "COLOR": "red",
        "SIZE": "small",
    }
    is_red = evaluate_expression('($COLOR == "red" || $COLOR == "green") && $SIZE != "big"', variables)
    assert is_red
