from typing import Dict, Tuple

PIPELINE_PERSISTED_VARIABLES = [
    "CI_PIPELINE_ID",
    "CI_PIPELINE_URL",
]

JOB_PERSISTED_VARIABLES = [
    "CI_JOB_ID",
    "CI_JOB_URL",
    "CI_JOB_TOKEN",
    "CI_JOB_STARTED_AT",
    "CI_REGISTRY_USER",
    "CI_REGISTRY_PASSWORD",
    "CI_REPOSITORY_URL",
    "CI_DEPLOY_USER",
    "CI_DEPLOY_PASSWORD",
]

NOT_RULE_EXPANDABLE = PIPELINE_PERSISTED_VARIABLES + JOB_PERSISTED_VARIABLES


def expand_for_rules(variables: Dict[str, str], value: str) -> Tuple[str, bool]:
    """Expand a variable if it is allowed to expand in a rules expression, else just return it"""
    defined = True
    if value and value.startswith("$"):
        name = value[1:].strip()
        if name not in NOT_RULE_EXPANDABLE:
            value = variables.get(name, "")
            defined = name in variables
    return value, defined
