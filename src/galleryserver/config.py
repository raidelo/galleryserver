from dataclasses import dataclass
from json import loads
from pathlib import Path
from typing import TypeIs

from galleryserver.constants import PACKAGE_NAME


@dataclass
class Config:
    blacklist: list[str] | None
    whitelist: list[str] | None


class ConfigParseError(Exception):
    pass


def _is_str_list(value: object) -> TypeIs[list[str]]:
    return isinstance(value, list) and all(isinstance(e, str) for e in value)


def load_config() -> Config | None:
    config_file = Path.home() / ".config" / PACKAGE_NAME / "config.json"

    try:
        content = loads(config_file.read_bytes())
    except FileNotFoundError:
        return None

    blacklist = content.get("blacklist")
    whitelist = content.get("whitelist")

    error_msg = (
        "error: el campo `{}` del archivo de configuración debe ser de tipo list[str]"
    )

    if not _is_str_list(blacklist) and not blacklist is None:
        raise ConfigParseError(error_msg.format("blacklist"))

    if not _is_str_list(whitelist) and not whitelist is None:
        raise ConfigParseError(error_msg.format("whitelist"))

    return Config(blacklist=blacklist, whitelist=whitelist)
