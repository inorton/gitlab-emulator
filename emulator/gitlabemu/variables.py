"""Helper functions for handling pipeline variable substitution"""
import re
from typing import Dict, Union, Any

VARIABLE_PATTERN = re.compile(r"(\$\w+)")


def expand_variable(variables: Dict[str, str], haystack: Union[str, Dict[str, Any]]) -> str:
    """Expand a $NAME style variable"""
    if isinstance(haystack, dict):
        if haystack.get("expand") is False:
            return haystack.get("value", "")
        # expandable variable
        haystack = haystack.get("value", "")

    while True:
        match = VARIABLE_PATTERN.search(haystack)
        if match:
            variable = match.group(0)
            if variable:
                name = variable[1:]
                value = expand_variable(variables, variables.get(name, ""))
                haystack = haystack.replace(variable, value)
        else:
            break
    return haystack
