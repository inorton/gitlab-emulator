"""
Logging functions
"""
from __future__ import print_function
import sys
import os
import logging
from .errors import GitlabEmulatorError

FORMAT = '%(asctime)-15s %(name)s  %(message)s'
logging.basicConfig(format=FORMAT)

LOGGER = logging.getLogger('gitlab-emulator')
LOGGER.setLevel(logging.INFO)

FATAL_EXIT = True

AFIRMATIVE = ["y", "yes", "1", "enabled", "on"]

def is_afirmative(txt: str) -> bool:
    return str(txt).lower() in AFIRMATIVE


def enable_rule_debug():
    os.environ["GLE_DEBUG_RULES"] = "y"

def enable_debug():
    os.environ["GLE_DEBUG"] = "y"


def info(msg):
    LOGGER.info(msg)

def debug_enabled() -> bool:
    return is_afirmative(os.environ.get("GLE_DEBUG", "n"))


def debugrule_enabled() -> bool:
    return is_afirmative(os.environ.get("GLE_DEBUG_RULES", "n"))


def debugrule(msg):
    if debugrule_enabled() or debug_enabled():
        LOGGER.info(f"D: {msg}")


def debug(msg):
    if debug_enabled():
        LOGGER.info(f"D: {msg}")


def warning(msg):
    LOGGER.warning(f"W! {msg}")


def fatal(msg):
    LOGGER.critical(f"E!: {msg}")
    if FATAL_EXIT:
        sys.exit(1)
    raise GitlabEmulatorError()
