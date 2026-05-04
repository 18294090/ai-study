from typing import Literal

ModelTier = Literal["reasoning", "general", "small", "long_ctx"]


class ModelRouter:
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def select(self, task: str) -> ModelTier:
        return {
            "domain_extract": "long_ctx",
            "verify": "reasoning",
            "pedagogical_tag": "general",
            "skill_map": "reasoning",
            "summary": "general",
            "embedding": "small",
        }.get(task, "general")