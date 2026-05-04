from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None

    def get_api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class Neo4jConfig:
    uri_env: str
    user_env: str
    password_env: str
    database: str = "neo4j"

    def get_uri(self) -> str:
        return os.environ.get(self.uri_env, "bolt://localhost:7687")
    def get_user(self) -> str:
        return os.environ.get(self.user_env, "neo4j")
    def get_password(self) -> str:
        return os.environ.get(self.password_env, "")


@dataclass
class QdrantConfig:
    url_env: str
    collection: str

    def get_url(self) -> str:
        return os.environ.get(self.url_env, "http://localhost:6333")


@dataclass
class ParsingConfig:
    default_parsers: list
    device: str


@dataclass
class EvalConfig:
    default_threshold: float
    min_f1: float


@dataclass
class KGConfig:
    llm: LLMConfig
    parsing: ParsingConfig
    storage: Dict[str, Any]
    eval: EvalConfig


def load_config(path: Path = CONFIG_PATH) -> KGConfig:
    with open(path) as f:
        data = yaml.safe_load(f)

    return KGConfig(
        llm=LLMConfig(**data["llm"]),
        parsing=ParsingConfig(**data["parsing"]),
        storage=data["storage"],
        eval=EvalConfig(**data["eval"]),
    )


_config: Optional[KGConfig] = None


def get_config() -> KGConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config