"""KG 配置 - 从统一 config.yaml 加载"""

from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


def get_root_config_path() -> Path:
    """获取根目录的 config.yaml 路径"""
    # backend/app/kg/src/ -> backend/app/kg/ -> backend/app/ -> backend/ -> project root
    return Path(__file__).resolve().parent.parent.parent.parent.parent / "config.yaml"


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
    uri_default: str = "bolt://localhost:7687"
    user_default: str = "neo4j"
    password_default: str = "12345678"

    def get_uri(self) -> str:
        return os.environ.get(self.uri_env, self.uri_default)
    def get_user(self) -> str:
        return os.environ.get(self.user_env, self.user_default)
    def get_password(self) -> str:
        return os.environ.get(self.password_env, self.password_default)


@dataclass
class QdrantConfig:
    url_env: str
    url_default: str = "http://localhost:6333"
    collection: str = "textbook_chunks"

    def get_url(self) -> str:
        return os.environ.get(self.url_env, self.url_default)


@dataclass
class ParsingConfig:
    default_parsers: list
    device: str


@dataclass
class EvalConfig:
    default_threshold: float
    min_f1: float


@dataclass
class EmbeddingConfig:
    provider: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None

    def get_api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class RerankerConfig:
    provider: str
    model: str
    api_key_env: str

    def get_api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class GeneratorConfig:
    default_model: str
    reasoning_model: str
    api_key_env: str

    def get_api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class RetrievalConfig:
    vector_top_k: int
    rerank_top_k: int


@dataclass
class GraphRAGConfig:
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    generator: GeneratorConfig
    retrieval: RetrievalConfig


@dataclass
class KGConfig:
    llm: LLMConfig
    parsing: ParsingConfig
    storage: Dict[str, Any]
    eval: EvalConfig
    graphrag: GraphRAGConfig


def load_config(path: Optional[Path] = None) -> KGConfig:
    if path is None:
        path = get_root_config_path()

    with open(path) as f:
        data = yaml.safe_load(f)

    storage_cfg = data.get("storage", {})

    return KGConfig(
        llm=LLMConfig(**data.get("llm", {})),
        parsing=ParsingConfig(**data.get("parsing", {})),
        storage=data.get("storage", {}),
        eval=EvalConfig(**data.get("eval", {})),
        graphrag=GraphRAGConfig(
            embedding=EmbeddingConfig(**data.get("graphrag", {}).get("embedding", {})),
            reranker=RerankerConfig(**data.get("graphrag", {}).get("reranker", {})),
            generator=GeneratorConfig(**data.get("graphrag", {}).get("generator", {})),
            retrieval=RetrievalConfig(**data.get("graphrag", {}).get("retrieval", {})),
        ),
    )


_config: Optional[KGConfig] = None


def get_config() -> KGConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config