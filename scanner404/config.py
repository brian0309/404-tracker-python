import configparser
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.ini")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config["scanner"] = {
        "threads": "5",
        "timeout": "10",
        "crawl_subpages": "1",
        "theme": "dark",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    config_path = Path(path)
    if config_path.exists():
        config.read(config_path)

    return config


def save_config(config: configparser.ConfigParser, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
    config_path = Path(path)
    with config_path.open("w", encoding="utf-8") as config_file:
        config.write(config_file)
