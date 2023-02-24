"""Expand !reference tags to values"""
from typing import Dict, Any, Union
from .gitlab.types import RESERVED_TOP_KEYS, DEFAULT_JOB_KEYS

from .yamlloader import GitlabReference, GitlabReferenceError

def process_references(baseobj: dict) -> dict:
    """Expand all jobs with references"""
    for jobname in baseobj.keys():
        if jobname not in RESERVED_TOP_KEYS:
            value = process_block_references(baseobj, baseobj[jobname])
            baseobj[jobname] = value
    return baseobj


def process_reference_value(baseobj: dict, item: Union[GitlabReference, int, str], depth: int = 0) -> Union[str, int, list]:
    """Process a reference"""
    if isinstance(item, GitlabReference):
        src = baseobj.get(item.job, None)
        if src is None:
            raise GitlabReferenceError(f"cannot find referent job for {item}")
        src = src.get(item.element, None)
        if src is None:
            raise GitlabReferenceError(f"cannot find referent key for {item}")
        if item.value:
            if not isinstance(src, dict):
                raise GitlabReferenceError(f"can only reference values from maps: {item}")
            src = src.get(item.value, None)
            if src is None:
                raise GitlabReferenceError(f"cannot find referent value for {item}")
        return src
    return item

def process_block_references(baseobj: dict, block: Dict[str, Any], depth: int = 0) -> dict:
    """In a job, expand all references"""
    if depth > 9:
        raise GitlabReferenceError("!references cannot be used more than 10 levels deep")

    for name, value in block.items():
        if isinstance(value, GitlabReference):
            block[name] = process_reference_value(baseobj, value, depth + 1)
        elif isinstance(value, list):
            value = [process_reference_value(baseobj, x, depth + 1) for x in value]
            # flatten the list
            flat_value = []
            for item in value:
                if isinstance(item, list):
                    flat_value.extend(item)
                else:
                    flat_value.append(item)
            block[name] = flat_value
        if isinstance(value, dict):
            value = process_block_references(baseobj, value, depth + 1)
            block[name] = value

    return block

