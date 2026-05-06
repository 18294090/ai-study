"""应用配置 - 从统一 config.yaml 加载"""

import os
import logging
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator
from pydantic_core import MultiHostUrl

# 项目根路径 (backend/ 的父目录)
ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent
# config.yaml 在项目根目录
CONFIG_PATH = ROOT_PATH / "config.yaml"


def load_yaml_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """加载 YAML 配置文件，支持 ${ENV_VAR} 插值"""
    with open(path) as f:
        raw = f.read()

    # 替换 ${ENV_VAR} 或 ${ENV_VAR:default}
    def replace_env_var(match):
        expr = match.group(1)
        if ":" in expr:
            env_var, default = expr.split(":", 1)
            return os.getenv(env_var.strip(), default.strip())
        return os.getenv(expr.strip(), "")

    import re
    content = re.sub(r'\$\{([^}]+)\}', replace_env_var, raw)
    return yaml.safe_load(content)


class Settings:
    """应用配置设置类 - 从 config.yaml 加载"""

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        if config_dict is None:
            config_dict = load_yaml_config()

        self._cfg = config_dict

        # ================== 应用基础配置 ==================
        app_cfg = config_dict.get("app", {})
        self.PROJECT_NAME = app_cfg.get("name", "题库管理系统")
        self.VERSION = app_cfg.get("version", "1.0.0")
        self.DESCRIPTION = app_cfg.get("description", "")
        self.ENV = app_cfg.get("env", "development")

        # ================== 服务器配置 ==================
        server_cfg = config_dict.get("server", {})
        self.HOST = server_cfg.get("host", "0.0.0.0")
        self.PORT = server_cfg.get("port", 8000)
        self.RELOAD = server_cfg.get("reload", False)
        self.WORKERS = server_cfg.get("workers", 1)

        # ================== API 配置 ==================
        api_cfg = config_dict.get("api", {})
        self.API_V1_PREFIX = api_cfg.get("v1_prefix", "/api/v1")
        self.API_INTERNAL_PREFIX = api_cfg.get("internal_prefix", "/internal")

        # ================== 文件上传配置 ==================
        upload_cfg = config_dict.get("upload", {})
        self.UPLOAD_DIR = upload_cfg.get("dir", "./uploads")
        self.MAX_UPLOAD_SIZE = upload_cfg.get("max_upload_size_mb", 5) * 1024 * 1024
        self.ALLOWED_UPLOAD_TYPES = upload_cfg.get("allowed_types", [])
        self.MEDIA_ROOT = upload_cfg.get("media_root", "./media")

        # ================== 数据库配置 ==================
        db_cfg = config_dict.get("database", {})
        self.DATABASE_URL: str = db_cfg.get("url", "postgresql+asyncpg://postgres:123@localhost:5432/mydb")
        self.SQLALCHEMY_DATABASE_URL: str = db_cfg.get("sqlalchemy_url", "postgresql://postgres:123@localhost:5432/mydb")
        self.DB_ECHO: bool = db_cfg.get("echo", False)
        self.CREATE_DB_TABLES: bool = db_cfg.get("create_tables", True)

        # ================== 安全配置 ==================
        security_cfg = config_dict.get("security", {})
        self.SECRET_KEY = security_cfg.get("secret_key", "secret-key-please-change-for-production")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = security_cfg.get("access_token_expire_minutes", 10080)
        self.REFRESH_TOKEN_EXPIRE_MINUTES = security_cfg.get("refresh_token_expire_minutes", 2592000)
        self.ALGORITHM = security_cfg.get("algorithm", "HS256")

        # ================== CORS 配置 ==================
        cors_cfg = config_dict.get("cors", {})
        self.CORS_ORIGINS = cors_cfg.get("origins", ["http://localhost:3000"])
        self.CORS_ALLOW_CREDENTIALS = cors_cfg.get("allow_credentials", True)
        self.CORS_ALLOW_METHODS = cors_cfg.get("allow_methods", ["*"])
        self.CORS_ALLOW_HEADERS = cors_cfg.get("allow_headers", ["*"])

        # ================== 日志配置 ==================
        logging_cfg = config_dict.get("logging", {})
        self.LOG_LEVEL = logging_cfg.get("level", "INFO")
        self.JSON_LOGS = logging_cfg.get("json_logs", False)
        self.LOG_FILE = logging_cfg.get("log_file")

        # ================== 缓存配置 ==================
        cache_cfg = config_dict.get("cache", {})
        self.REDIS_URL = cache_cfg.get("redis_url", "redis://localhost:6379/0")
        self.CACHE_TTL = cache_cfg.get("ttl", 300)

        # ================== 任务队列配置 ==================
        celery_cfg = config_dict.get("celery", {})
        self.CELERY_BROKER_URL = celery_cfg.get("broker_url", "redis://localhost:6379/1")
        self.CELERY_RESULT_BACKEND = celery_cfg.get("result_backend", "redis://localhost:6379/2")

        # ================== LLM 配置 ==================
        llm_cfg = config_dict.get("llm", {})
        self.LLM_PROVIDER = llm_cfg.get("provider", "openai")
        self.LLM_MODEL = llm_cfg.get("model", "gpt-4o")
        self.LLM_API_KEY_ENV = llm_cfg.get("api_key_env", "OPENAI_API_KEY")
        self.LLM_BASE_URL = llm_cfg.get("base_url", "https://api.openai.com/v1")

        ollama_cfg = config_dict.get("ollama", {})
        self.OLLAMA_BASE_URL = ollama_cfg.get("base_url", "http://localhost:11434")

        # ================== PDF 解析配置 ==================
        parsing_cfg = config_dict.get("parsing", {})
        self.PARSING_DEVICE = parsing_cfg.get("device", "cuda")
        self.DEFAULT_PARSERS = parsing_cfg.get("default_parsers", ["mineru", "marker", "docling"])

        # ================== Neo4j 配置 ==================
        neo4j_cfg = config_dict.get("storage", {}).get("neo4j", {})
        self.NEO4J_URI = os.getenv(neo4j_cfg.get("uri_env", "NEO4J_URI"), neo4j_cfg.get("uri_default", "bolt://localhost:7687"))
        self.NEO4J_USER = os.getenv(neo4j_cfg.get("user_env", "NEO4J_USER"), neo4j_cfg.get("user_default", "neo4j"))
        self.NEO4J_PASSWORD = os.getenv(neo4j_cfg.get("password_env", "NEO4J_PASSWORD"), neo4j_cfg.get("password_default", "12345678"))

        # ================== Qdrant 配置 ==================
        qdrant_cfg = config_dict.get("storage", {}).get("qdrant", {})
        self.QDRANT_URL = os.getenv(qdrant_cfg.get("url_env", "QDRANT_URL"), qdrant_cfg.get("url_default", "http://localhost:6333"))
        self.QDRANT_COLLECTION = qdrant_cfg.get("collection", "textbook_chunks")

        # ================== 评估配置 ==================
        eval_cfg = config_dict.get("eval", {})
        self.EVAL_DEFAULT_THRESHOLD = eval_cfg.get("default_threshold", 0.7)
        self.EVAL_MIN_F1 = eval_cfg.get("min_f1", 0.5)

        # ================== GraphRAG 配置 ==================
        graphrag_cfg = config_dict.get("graphrag", {})
        self.GRAPH_EMBEDDING_PROVIDER = graphrag_cfg.get("embedding", {}).get("provider", "bge-m3")
        self.GRAPH_EMBEDDING_MODEL = graphrag_cfg.get("embedding", {}).get("model", "BAAI/bge-m3")
        self.GRAPH_EMBEDDING_API_KEY_ENV = graphrag_cfg.get("embedding", {}).get("api_key_env", "OPENAI_API_KEY")
        self.GRAPH_EMBEDDING_BASE_URL = graphrag_cfg.get("embedding", {}).get("base_url", "http://localhost:8000/v1")

        self.GRAPH_RERANKER_PROVIDER = graphrag_cfg.get("reranker", {}).get("provider", "cohere")
        self.GRAPH_RERANKER_MODEL = graphrag_cfg.get("reranker", {}).get("model", "rerank-v3")
        self.GRAPH_RERANKER_API_KEY_ENV = graphrag_cfg.get("reranker", {}).get("api_key_env", "COHERE_API_KEY")

        self.GRAPH_GENERATOR_MODEL = graphrag_cfg.get("generator", {}).get("default_model", "gpt-4o")
        self.GRAPH_REASONING_MODEL = graphrag_cfg.get("generator", {}).get("reasoning_model", "o3")
        self.GRAPH_GENERATOR_API_KEY_ENV = graphrag_cfg.get("generator", {}).get("api_key_env", "OPENAI_API_KEY")

        self.GRAPH_VECTOR_TOP_K = graphrag_cfg.get("retrieval", {}).get("vector_top_k", 30)
        self.GRAPH_RERANK_TOP_K = graphrag_cfg.get("retrieval", {}).get("rerank_top_k", 10)

        # ================== Hermes 配置 ==================
        hermes_cfg = config_dict.get("hermes", {})
        self.HERMES_RUNTIME_HOST = hermes_cfg.get("runtime", {}).get("host", "127.0.0.1")
        self.HERMES_RUNTIME_PORT = hermes_cfg.get("runtime", {}).get("port", 8080)
        self.HERMES_MAX_ITERATIONS = hermes_cfg.get("runtime", {}).get("max_iterations", 90)
        self.HERMES_TIMEOUT = hermes_cfg.get("runtime", {}).get("timeout", 300)

        self.HERMES_MEMORY_TYPE = hermes_cfg.get("memory", {}).get("type", "sqlite")
        self.HERMES_MEMORY_PATH = hermes_cfg.get("memory", {}).get("path", "~/.hermes/memory.db")

        exam_skill_cfg = hermes_cfg.get("skills", {}).get("exam_skill", {})
        self.HERMES_EXAM_SKILL_ENABLED = exam_skill_cfg.get("enabled", True)
        self.HERMES_EXAM_CONFIDENCE_THRESHOLD = exam_skill_cfg.get("confidence_threshold", 0.6)

        self.HERMES_PROVIDER_DEFAULT = hermes_cfg.get("providers", {}).get("default", "openrouter")
        self.HERMES_OPENROUTER_API_KEY_ENV = hermes_cfg.get("providers", {}).get("openrouter", {}).get("api_key", "OPENROUTER_API_KEY")
        self.HERMES_OPENROUTER_MODEL = hermes_cfg.get("providers", {}).get("openrouter", {}).get("model", "deepseek/deepseek-chat-v3")

        # ================== 功能开关 ==================
        features_cfg = config_dict.get("features", {})
        self.DOCS_ENABLED = features_cfg.get("docs_enabled", True)
        self.TESTING = features_cfg.get("testing", False)
        self.DEBUG = features_cfg.get("debug", False)
        self.PROMETHEUS_ENABLED = features_cfg.get("prometheus_enabled", True)
        self.PROMETHEUS_METRICS_PATH = features_cfg.get("prometheus_metrics_path", "/internal/metrics")

        # ================== 管理账户 ==================
        self.FIRST_SUPERUSER: EmailStr = "admin@example.com"
        self.FIRST_SUPERUSER_PASSWORD: str = "changeme"

        # 原始配置供后续访问
        self._raw_config = config_dict

    def get_raw_config(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._raw_config

    def get_hermes_config(self) -> Dict[str, Any]:
        """获取 Hermes 配置部分"""
        return self._raw_config.get("hermes", {})

    def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置部分"""
        return self._raw_config.get("llm", {})

    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置部分"""
        return self._raw_config.get("storage", {})


# 全局配置实例
_settings: Optional[Settings] = None


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（带缓存）"""
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
            logging.info(f"Loaded config from {CONFIG_PATH}")
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            raise
    return _settings


# 快捷访问
settings = get_settings()


def setup_app_logging(config: Settings) -> None:
    """配置应用日志"""
    from app.core.logging import setup_logging
    setup_logging(config)


# 如果直接运行此文件，则打印配置
if __name__ == "__main__":
    import json
    s = Settings()
    print(json.dumps(s._raw_config, indent=2, ensure_ascii=False))