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


def enable_rule_debug():
    os.environ["GLE_DEBUG_RULES"] = "y"


def info(msg):
    LOGGER.info(msg)


def debugrule(msg):
    if os.environ.get("GLE_DEBUG_RULES", "n") != "n":
        LOGGER.info(f"D: {msg}")


def warning(msg):
    LOGGER.warning(f"W! {msg}")


def fatal(msg):
    LOGGER.critical(f"E!: {msg}")
    if FATAL_EXIT:
        sys.exit(1)
    raise GitlabEmulatorError()
