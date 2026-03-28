import configparser
import os
from pathlib import Path

LOCAL_CONFIG_PATH = Path("config.ini")


def _default_config_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Scanner404" / "config.ini"
    return LOCAL_CONFIG_PATH


DEFAULT_CONFIG_PATH = _default_config_path()


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config["scanner"] = {
        "threads": "5",
        "timeout": "10",
        "crawl_subpages": "1",
        "theme": "dark",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    # Prefer explicit/default path, but also support legacy local config.ini files.
    candidate_paths: list[Path] = []
    config_path = Path(path)
    candidate_paths.append(config_path)

    if config_path.resolve() != LOCAL_CONFIG_PATH.resolve() and LOCAL_CONFIG_PATH.exists():
        candidate_paths.append(LOCAL_CONFIG_PATH)

    for candidate in candidate_paths:
        if candidate.exists():
            config.read(candidate)
            break

    return config


def save_config(config: configparser.ConfigParser, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as config_file:
        config.write(config_file)
