"""Helper functions for handling pipeline variable substitution"""
import re
from typing import Dict

VARIABLE_PATTERN = re.compile(r"(\$\w+)")


def expand_variable(variables: Dict[str, str], haystack: str) -> str:
    """Expand a $NAME style variable"""
    while True:
        match = VARIABLE_PATTERN.search(haystack)
        if match:
            variable = match.group(0)
            if variable:
                name = variable[1:]
                value = variables.get(name, "")
                haystack = haystack.replace(variable, value)
        else:
            break
    return haystack
