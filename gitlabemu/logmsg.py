"""
Logging functions
"""
from __future__ import print_function
import sys
import logging

FORMAT = '%(asctime)-15s %(name)s  %(message)s'
logging.basicConfig(format=FORMAT)

LOGGER = logging.getLogger('gitlab-emulator')

def info(msg):
    LOGGER.info(msg)

def warning(msg):
    LOGGER.warning(msg)

def fatal(msg):
    LOGGER.critical(msg)
    sys.exit(1)