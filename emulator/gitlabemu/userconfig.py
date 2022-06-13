import os
import sys
from typing import Optional, List

import yaml
from .logmsg import fatal, info

USER_CFG_ENV = "GLE_CONFIG"
USER_CFG_DIR = os.environ.get("LOCALAPPDATA", os.environ.get("HOME", os.getcwd()))
USER_CFG_DEFAULT = os.path.join(USER_CFG_DIR, ".gle", "emulator.yml")

_userconfig = {}


def reset_user_config():
    _userconfig.clear()


def get_user_config_path() -> str:
    cfg = os.environ.get(USER_CFG_ENV, None)
    if not cfg:
        cfg = USER_CFG_DEFAULT
    return cfg


def load_user_config(force_reload: Optional[bool] = False) -> dict:
    """
    Load user configuration
    if force_reload is True, load the file from disk and ignore any GLE env vars except GLE_CONFIG
    :return:
    """
    if not force_reload:
        if len(_userconfig):
            return _userconfig

    cfg = get_user_config_path()
    data = {}
    if os.path.exists(cfg):
        print(f"Reading gle config from {cfg}", file=sys.stderr)
        with open(cfg, "r") as ycfg:
            data = yaml.safe_load(ycfg)

    if "emulator" not in data:
        data["emulator"] = {}

    current_context = get_current_user_context(data)

    # overrides from env vars
    volumes = os.environ.get("GLE_DOCKER_VOLUMES", None)
    if volumes is not None:
        if not force_reload:
            info("Using GLE_DOCKER_VOLUMES from environment")
            # empty string or set to a value
            if "volumes" in data[current_context].get("docker", {}):
                del data[current_context]["docker"]["volumes"]

            # set new value
            if volumes:
                if "docker" not in data["emulator"]:
                    data[current_context]["docker"] = {}
                data[current_context]["docker"]["volumes"] = volumes.split(",")

    _userconfig.clear()
    for name in data:
        _userconfig[name] = data[name]
    return dict(_userconfig)


def override_user_config_value(section, name, value):
    if section not in _userconfig:
        _userconfig[section] = {}
    _userconfig[section][name] = value


def get_current_user_context(cfg: dict) -> str:
    """Get the currently set context name"""
    current_context = os.getenv("GLE_CONTEXT", None)
    if current_context == "current_context":
        fatal("'current_context' is not allowed for GLE_CONFIG")
    if current_context is None:
        current_context = cfg.get("current_context", "emulator")
    return current_context


def get_user_contexts(cfg: dict) -> List[str]:
    """Get the list of available configs"""
    top_levels = [x for x in cfg.keys() if x != "current_context"]
    if "emulator" not in top_levels:
        top_levels.append("emulator")
    return list(sorted(top_levels))


def get_user_config_value(cfg: dict, section: str, *, name=None, default=None):
    """
    Read a config value
    :param cfg:
    :param section:
    :param name:
    :param default:
    :return:
    """
    current_context = get_current_user_context(cfg)
    cfgdata = cfg.get(current_context, {})
    if cfgdata:
        sectiondata = cfgdata.get(section, {})
        if sectiondata:
            if not name:
                return sectiondata
            return sectiondata.get(name, default)
    return default


def set_context(data: dict, context: str) -> str:
    """Set the current context and return the name"""

    if context == "current_context":
        fatal("'current_context' is not a permitted context name")

    if context in ["default", "emulator"]:
        context = "emulator"

    if context not in data:
        data[context] = {}

    data["current_context"] = context

    return context


def save_userconfig(data: dict) -> str:
    """Save the config data"""
    cfg = get_user_config_path()
    folder = os.path.dirname(cfg)
    if not os.path.exists(folder):
        os.makedirs(folder)
    with open(cfg, "w") as ydata:
        yaml.safe_dump(data, ydata, indent=2, width=120, default_flow_style=False)

    return cfg
