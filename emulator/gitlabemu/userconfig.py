import os
import sys

import yaml


USER_CFG_ENV = "GLE_CONFIG"
USER_CFG_DIR = os.environ.get("LOCALAPPDATA", os.environ.get("HOME", os.getcwd()))
USER_CFG_DEFAULT = os.path.join(USER_CFG_DIR, ".gle", "emulator.yml")

_userconfig = {}


def reset_user_config():
    _userconfig.clear()


def load_user_config() -> dict:
    """
    Load user configuration
    :return:
    """
    if len(_userconfig):
        return _userconfig

    cfg = os.environ.get(USER_CFG_ENV, None)
    if not cfg:
        cfg = USER_CFG_DEFAULT
    data = {}
    if os.path.exists(cfg):
        print(f"Reading gle config from {cfg}", file=sys.stderr)
        with open(cfg, "r") as ycfg:
            data = yaml.safe_load(ycfg)

    if "emulator" not in data:
        data["emulator"] = {}

    # overrides from env vars
    volumes = os.environ.get("GLE_DOCKER_VOLUMES", None)
    if volumes is not None:
        # empty string or set to a value
        if "volumes" in data["emulator"].get("docker", {}):
            del data["emulator"]["docker"]["volumes"]

        # set new value
        if volumes:
            if "docker" not in data["emulator"]:
                data["emulator"]["docker"] = {}
            data["emulator"]["docker"]["volumes"] = volumes.split(",")

    _userconfig.clear()
    for name in data:
        _userconfig[name] = data[name]

    return dict(_userconfig)


def override_user_config_value(section, name, value):
    if section not in _userconfig:
        _userconfig[section] = {}
    _userconfig[section][name] = value


def get_user_config_value(cfg: dict, section: str, *, name=None, default=None):
    """
    Read a config value
    :param cfg:
    :param section:
    :param name:
    :param default:
    :return:
    """
    cfgdata = cfg.get("emulator", {})
    if cfgdata:
        sectiondata = cfgdata.get(section, {})
        if sectiondata:
            if not name:
                return sectiondata
            return sectiondata.get(name, default)
    return default
