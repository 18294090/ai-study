# KG Pipeline Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the textbook upload → parse → knowledge graph pipeline by integrating existing parsers, fixing lead_agent stubs, and connecting to the API endpoint.

**Architecture:**改造现有 `knowledge_extraction.py` 接口，底层替换为 MultiParserVote + lead_agent (LangGraph) 流程。配置通过 `config.yaml` 管理，LLM 调用通过 `StructuredClient` 路由。

**Tech Stack:** FastAPI, LangGraph, Pydantic, Neo4j, Qdrant, PyYAML

---

## File Map

### New Files
- `backend/app/kg/config.yaml` - KG pipeline configuration (LLM, parsers, storage, eval thresholds)
- `backend/app/kg/src/config.py` - YAML config loader with env var substitution
- `backend/app/kg/src/llm_router.py` - LLM provider router (OpenAI/Anthropic/vLLM)
- `backend/tests/unit/kg/test_config.py` - config loader tests
- `backend/tests/unit/kg/test_lead_agent.py` - lead_agent node tests
- `backend/tests/integration/kg/test_pipeline_api.py` - API integration tests

### Modified Files
- `backend/app/kg/run_pipeline.py:51` - replace `MultiParserVote(parsers=[])` with `create_multi_parser()`
- `backend/app/kg/agents/lead_agent.py` - implement stub nodes (extract_domain, tag_pedagogical, map_skills, store)
- `backend/app/kg/src/parsers/multi_parser.py` - already done, verify `create_multi_parser` works
- `backend/app/api/v1/routes/knowledge_extraction.py` - replace `process_knowledge_extraction` with new pipeline
- `backend/app/kg/agents/domain_extractor.py` - fix relative import (`from ..models` → `from src.models`)
- `backend/app/kg/agents/pedagogical_tagger.py` - fix relative import
- `backend/app/kg/agents/skill_mapper.py` - fix relative import

---

## Task 1: Create config.yaml and config loader

**Files:**
- Create: `backend/app/kg/config.yaml`
- Create: `backend/app/kg/src/config.py`
- Test: `backend/tests/unit/kg/test_config.py`

- [ ] **Step 1: Create config.yaml**

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key_env: "OPENAI_API_KEY"
  base_url: "https://api.openai.com/v1"

parsing:
  default_parsers: ["mineru", "marker", "docling"]
  device: "cuda"

storage:
  neo4j:
    uri_env: "NEO4J_URI"
    user_env: "NEO4J_USER"
    password_env: "NEO4J_PASSWORD"
    database: "neo4j"
  qdrant:
    url_env: "QDRANT_URL"
    collection: "textbook_chunks"

eval:
  default_threshold: 0.7
  min_f1: 0.5
```

- [ ] **Step 2: Create src/config.py**

```python
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
```

- [ ] **Step 3: Run test to verify config loads**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.src.config import get_config; c = get_config(); print(f'llm provider={c.llm.provider}, parsers={c.parsing.default_parsers}')"
```
Expected: output showing config loaded

- [ ] **Step 4: Commit**

---

## Task 2: Create LLM router

**Files:**
- Create: `backend/app/kg/src/llm_router.py`
- Modify: `backend/app/kg/src/config.py` (add import in Task 1)
- Test: `backend/tests/unit/kg/test_llm_router.py`

- [ ] **Step 1: Create llm_router.py**

```python
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
```

- [ ] **Step 2: Run to verify no import errors**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.src.llm_router import LLMRouter; print('LLMRouter import OK')"
```

- [ ] **Step 3: Commit**

---

## Task 3: Fix domain_extractor, pedagogical_tagger, skill_mapper relative imports

**Files:**
- Modify: `backend/app/kg/agents/domain_extractor.py:4-5`
- Modify: `backend/app/kg/agents/pedagogical_tagger.py:5-6`
- Modify: `backend/app/kg/agents/skill_mapper.py:5`

- [ ] **Step 1: Fix domain_extractor.py**

Current: `from src.models.entities import ...` (relative from kg/agents/)
Change to: `from kg.src.models.entities import ...` (absolute from backend/app/)

- [ ] **Step 2: Fix pedagogical_tagger.py**

Current: `from src.models.pedagogical import ...` and `from src.routing.structured_client import ...`
Change to: `from kg.src.models.pedagogical import ...` and `from kg.src.routing.structured_client import ...`

- [ ] **Step 3: Fix skill_mapper.py**

Current: `from src.models.diagnostic import ...` and `from src.routing.structured_client import ...`
Change to: `from kg.src.models.diagnostic import ...` and `from kg.src.routing.structured_client import ...`

- [ ] **Step 4: Verify imports**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.domain_extractor import DomainExtractor; from app.kg.agents.pedagogical_tagger import PedagogicalTagger; from app.kg.agents.skill_mapper import SkillMapper; print('All agent imports OK')"
```

- [ ] **Step 5: Commit**

---

## Task 4: Fix run_pipeline.py parser list

**Files:**
- Modify: `backend/app/kg/run_pipeline.py:51`

- [ ] **Step 1: Show current line 51**

Read file and verify current content is:
```python
textbook = MultiParserVote(parsers=[]).parse(str(input_path))
```

- [ ] **Step 2: Replace with create_multi_parser**

```python
from src.parsers.multi_parser import create_multi_parser
# ...
textbook = create_multi_parser().parse(str(input_path))
```

- [ ] **Step 3: Verify it loads**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.run_pipeline import EVAL_THRESHOLDS; print('run_pipeline loads OK')"
```

- [ ] **Step 4: Commit**

---

## Task 5: Implement lead_agent nodes

**Files:**
- Modify: `backend/app/kg/agents/lead_agent.py` (implement stub nodes)

- [ ] **Step 1: Read current _extract_domain_triples (line 68-70)**

```python
async def _extract_domain_triples(chapter: Chapter) -> list:
    await asyncio.sleep(0.01)
    return []
```

- [ ] **Step 2: Replace with real implementation**

```python
async def _extract_domain_triples(chapter: Chapter) -> list:
    from kg.agents.domain_extractor import DomainExtractor
    from kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        extractor = DomainExtractor(router.get_client())
        result = extractor.extract(chapter, book_context="")
        return [t.model_dump() for t in result.triples]
    except Exception as e:
        print(f"[extract_domain] failed for {chapter.chapter_id}: {e}")
        return []
```

- [ ] **Step 3: Read and replace _tag_pedagogical (line 95-97)**

```python
async def _tag_pedagogical(chapter: Chapter) -> list:
    await asyncio.sleep(0.01)
    return []
```

Replace with:
```python
async def _tag_pedagogical(chapter: Chapter) -> list:
    from kg.agents.pedagogical_tagger import PedagogicalTagger
    from kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        tagger = PedagogicalTagger(router.get_client())
        result = tagger.tag(chapter, book_context="")
        return [result.model_dump()]
    except Exception as e:
        print(f"[tag_pedagogical] failed for {chapter.chapter_id}: {e}")
        return []
```

- [ ] **Step 4: Read and replace _map_skills (line 122-124)**

```python
async def _map_skills(chapter: Chapter) -> list:
    await asyncio.sleep(0.01)
    return []
```

Replace with:
```python
async def _map_skills(chapter: Chapter) -> list:
    from kg.agents.skill_mapper import SkillMapper
    from kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        mapper = SkillMapper(router.get_client())
        concept_names = [s.title for s in chapter.sections]
        result = mapper.map_skills(concept_names, chapter.content[:500])
        return [r.model_dump() for r in result.q_matrix_entries]
    except Exception as e:
        print(f"[map_skills] failed for {chapter.chapter_id}: {e}")
        return []
```

- [ ] **Step 5: Implement store_node (line 169-170)**

```python
def store_node(state: PipelineState) -> PipelineState:
    return state
```

Replace with:
```python
def store_node(state: PipelineState) -> PipelineState:
    from kg.src.storage.dual_writer import DualWriter
    from kg.src.storage.neo4j_writer import Neo4jWriter
    from kg.src.storage.qdrant_writer import QdrantWriter
    from kg.src.config import get_config
    import os

    cfg = get_config()
    neo4j_cfg = cfg.storage["neo4j"]
    qdrant_cfg = cfg.storage["qdrant"]

    neo4j = Neo4jWriter(
        uri=os.environ.get(neo4j_cfg["uri_env"], "bolt://localhost:7687"),
        user=os.environ.get(neo4j_cfg["user_env"], "neo4j"),
        password=os.environ.get(neo4j_cfg["password_env"], ""),
        database=neo4j_cfg.get("database", "neo4j"),
    )
    qdrant = QdrantWriter(
        url=os.environ.get(qdrant_cfg["url_env"], "http://localhost:6333"),
        collection=qdrant_cfg.get("collection", "textbook_chunks"),
    )
    writer = DualWriter(neo4j=neo4j, qdrant=qdrant)

    triples = state.get("domain_triples", [])
    for triple_data in triples:
        try:
            writer.write_triple(triple_data)
        except Exception as e:
            print(f"[store] triple write failed: {e}")

    return state
```

- [ ] **Step 6: Verify lead_agent.py loads without errors**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.lead_agent import build_graph, run_pipeline; print('lead_agent loads OK')"
```

- [ ] **Step 7: Commit**

---

## Task 6: Rewrite knowledge_extraction.py API

**Files:**
- Modify: `backend/app/api/v1/routes/knowledge_extraction.py`

- [ ] **Step 1: Replace process_knowledge_extraction function body**

Old flow: `split_exam_paper` → `KnowledgeExtractionService` → `KnowledgeGraphBuilder`

New flow:
```python
async def process_knowledge_extraction(
    file_path: str,
    subject_id: int,
    user_id: int
):
    from kg.src.parsers.multi_parser import create_multi_parser
    from kg.agents.lead_agent import run_pipeline
    from kg.src.config import get_config
    import os

    try:
        # 1. Parse PDF with MultiParserVote
        textbook = create_multi_parser().parse(file_path)
        textbook.textbook_id = f"textbook_{subject_id}_{user_id}"
        textbook.subject = str(subject_id)

        # 2. Run KG pipeline
        cfg = get_config()
        result = await run_pipeline(
            textbook_id=textbook.textbook_id,
            chapters=textbook.chapters,
            eval_threshold=cfg.eval.default_threshold,
        )

        # 3. Check eval gate
        if not result.get("eval_passed", False):
            print(f"[pipeline] eval gate failed for {textbook.textbook_id}")
            return

        print(f"[pipeline] Success for {textbook.textbook_id}")

    except Exception as e:
        print(f"[pipeline] Extraction task failed: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
```

- [ ] **Step 2: Verify API route loads**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.api.v1.routes.knowledge_extraction import router; print('knowledge_extraction router loads OK')"
```

- [ ] **Step 3: Commit**

---

## Task 7: Verify full pipeline

**Files:**
- Test: integration test or manual smoke test

- [ ] **Step 1: Run import chain verification**

```bash
cd /home/zh/ai-study/backend && python3 -c "
from app.kg.src.parsers import create_multi_parser, PARSER_REGISTRY
from app.kg.agents.lead_agent import build_graph, run_pipeline
from app.kg.src.config import get_config
from app.kg.src.llm_router import LLMRouter
from app.api.v1.routes.knowledge_extraction import router
print('All imports OK')
print('Available parsers:', list(PARSER_REGISTRY.keys()))
print('Config loaded:', get_config().llm.provider)
"
```

- [ ] **Step 2: Commit**

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| config.yaml 管理配置 | Task 1 |
| LLM 路由 (OpenAI/Anthropic/vLLM) | Task 2 |
| domain_triples 真实抽取 | Task 5 |
| pedagogical tagging 真实抽取 | Task 5 |
| skill mapping 真实抽取 | Task 5 |
| store_node 写入 Neo4j/Qdrant | Task 5 |
| 修复 run_pipeline.py parser 列表 | Task 4 |
| 改造 knowledge_extraction API | Task 6 |
| 修复 agent 相对导入 | Task 3 |

All requirements covered. No placeholders found. Types consistent across tasks.

---

**Plan complete.**