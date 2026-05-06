"""Hermes runtime configuration."""

from pathlib import Path
from typing import Optional
import yaml


class HermesConfig:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "hermes" / "config.yaml"
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return self._default_config()
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _default_config(self) -> dict:
        return {
            "hermes": {
                "runtime": {"host": "127.0.0.1", "port": 8080},
                "skills": {"exam_skill": {"enabled": True, "confidence_threshold": 0.6}},
                "providers": {"default": "openrouter"},
            }
        }

    def get(self, key: str, default=None):
        keys = key.split(".")
        value = self._config
        for k in keys:
            value = value.get(k, default)
        return value


_config: Optional[HermesConfig] = None


def get_hermes_config() -> HermesConfig:
    global _config
    if _config is None:
        _config = HermesConfig()
    return _config
