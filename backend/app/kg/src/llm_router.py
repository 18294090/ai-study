from __future__ import annotations
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from .config import get_config


class LLMRouter:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        cfg = get_config()
        self.provider = provider or cfg.llm.provider
        self.model = model or cfg.llm.model
        self._client = None

    def get_client(self):
        if self._client is not None:
            return self._client

        cfg = get_config()
        if self.provider == "openai":
            self._client = ChatOpenAI(
                model=self.model,
                api_key=cfg.llm.get_api_key(),
                base_url=cfg.llm.base_url,
            )
        elif self.provider == "anthropic":
            self._client = ChatAnthropic(
                model=self.model,
                api_key=cfg.llm.get_api_key(),
            )
        elif self.provider == "vllm":
            self._client = ChatOpenAI(
                model=self.model,
                api_key="EMPTY",
                base_url=cfg.llm.base_url or "http://localhost:8000/v1",
            )
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        return self._client