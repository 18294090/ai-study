"""Hermes runtime configuration - 从统一 config.yaml 加载"""

from typing import Dict, Any, Optional


class HermesConfig:
    """Hermes 配置类 - 从 Settings 读取"""

    def __init__(self, settings=None):
        from app.core.config import get_settings as _get_settings
        self._settings = settings or _get_settings()
        self._hermes_cfg = self._settings.get_hermes_config()

    def get(self, key: str, default=None) -> Any:
        """获取配置值，支持 dot notation (如 'runtime.host')"""
        keys = key.split(".")
        value = self._hermes_cfg
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value if value is not None else default

    @property
    def runtime_host(self) -> str:
        return self._settings.HERMES_RUNTIME_HOST

    @property
    def runtime_port(self) -> int:
        return self._settings.HERMES_RUNTIME_PORT

    @property
    def max_iterations(self) -> int:
        return self._settings.HERMES_MAX_ITERATIONS

    @property
    def timeout(self) -> int:
        return self._settings.HERMES_TIMEOUT

    @property
    def memory_type(self) -> str:
        return self._settings.HERMES_MEMORY_TYPE

    @property
    def memory_path(self) -> str:
        return self._settings.HERMES_MEMORY_PATH

    @property
    def exam_skill_enabled(self) -> bool:
        return self._settings.HERMES_EXAM_SKILL_ENABLED

    @property
    def exam_confidence_threshold(self) -> float:
        return self._settings.HERMES_EXAM_CONFIDENCE_THRESHOLD

    @property
    def provider_default(self) -> str:
        return self._settings.HERMES_PROVIDER_DEFAULT

    @property
    def openrouter_api_key_env(self) -> str:
        return self._settings.HERMES_OPENROUTER_API_KEY_ENV

    @property
    def openrouter_model(self) -> str:
        return self._settings.HERMES_OPENROUTER_MODEL

    def get_provider_api_key(self) -> str:
        """获取 provider API key 从环境变量"""
        import os
        api_key_env = self.openrouter_api_key_env
        return os.getenv(api_key_env, "")


_config: Optional[HermesConfig] = None


def get_hermes_config() -> HermesConfig:
    global _config
    if _config is None:
        _config = HermesConfig()
    return _config