import os
from typing import Optional
from .userconfigdata import UserConfigFile, UserContext
from .logmsg import fatal

USER_CFG_ENV = "GLE_CONFIG"
USER_CFG_DIR = os.environ.get("LOCALAPPDATA", os.environ.get("HOME", os.getcwd()))
USER_CFG_DEFAULT = os.path.join(USER_CFG_DIR, ".gle", "emulator.yml")


def get_user_config_path() -> str:
    cfg = os.environ.get(USER_CFG_ENV, None)
    if not cfg:
        cfg = USER_CFG_DEFAULT
    return cfg


def get_user_config(filename: Optional[str] = None) -> UserConfigFile:
    config = UserConfigFile()
    if filename is None:
        filename = get_user_config_path()
    config.load(filename)
    return config


def get_user_config_context() -> UserContext:
    cfg = get_user_config()
    return cfg.contexts[cfg.current_context]


def get_current_user_context() -> str:
    """Get the currently set context name"""
    current_context = os.getenv("GLE_CONTEXT", None)
    if current_context == "current_context":
        fatal("'current_context' is not allowed for GLE_CONFIG")
    if current_context is None:
        current_context = get_user_config().current_context
    return current_context
