"""
Logging functions
"""
from __future__ import print_function
import sys
import logging
from .errors import GitlabEmulatorError

FORMAT = '%(asctime)-15s %(name)s  %(message)s'
logging.basicConfig(format=FORMAT)

LOGGER = logging.getLogger('gitlab-emulator')
LOGGER.setLevel(logging.INFO)

FATAL_EXIT = True


def info(msg):
    LOGGER.info(msg)

def warning(msg):
    LOGGER.warning(msg)

def fatal(msg):
    LOGGER.critical(msg)
    if FATAL_EXIT:
        sys.exit(1)
    raise GitlabEmulatorError()
