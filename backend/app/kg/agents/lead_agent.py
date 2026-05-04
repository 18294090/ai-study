from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Any, Optional
import asyncio
from app.kg.src.models import Textbook, Chapter


class PipelineState(TypedDict):
    textbook_id: str
    chapters: list
    domain_triples: list
    pedagogical: list
    skills: list
    resolved_entities: list
    communities: list
    eval_passed: bool
    eval_report: dict


def parse_node(state: PipelineState) -> PipelineState:
    from app.kg.src.parsers.multi_parser import MultiParserVote

    textbook_id = state["textbook_id"]
    chapters = state.get("chapters", [])
    if chapters:
        return state
    raise NotImplementedError("parse_node requires a PDF path - use parser directly")


async def _extract_with_retry(
    func,
    arg,
    max_retries: int = 3,
    **kwargs
) -> Any:
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func(arg, **kwargs) if asyncio.iscoroutinefunction(func) else func(arg, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_error


async def extract_domain_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    results = []
    semaphore = asyncio.Semaphore(3)

    async def process_chapter(chapter: Chapter) -> list:
        async with semaphore:
            for attempt in range(3):
                try:
                    return await _extract_domain_triples(chapter)
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            return []

    tasks = [process_chapter(ch) for ch in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    state["domain_triples"] = [r for r in results if isinstance(r, list) and not isinstance(r, Exception)]
    return state


async def _extract_domain_triples(chapter: Chapter) -> list:
    from app.kg.agents.domain_extractor import DomainExtractor
    from app.kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        extractor = DomainExtractor(router.get_client())
        result = extractor.extract(chapter, book_context="")
        return [t.model_dump() for t in result.triples]
    except Exception as e:
        print(f"[extract_domain] failed for {chapter.chapter_id}: {e}")
        return []


async def tag_pedagogical_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    results = []
    semaphore = asyncio.Semaphore(3)

    async def process_chapter(chapter: Chapter) -> list:
        async with semaphore:
            for attempt in range(3):
                try:
                    return await _tag_pedagogical(chapter)
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            return []

    tasks = [process_chapter(ch) for ch in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    state["pedagogical"] = [r for r in results if isinstance(r, list) and not isinstance(r, Exception)]
    return state


async def _tag_pedagogical(chapter: Chapter) -> list:
    from app.kg.agents.pedagogical_tagger import PedagogicalTagger
    from app.kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        tagger = PedagogicalTagger(router.get_client())
        result = tagger.tag(chapter, book_context="")
        return [result.model_dump()]
    except Exception as e:
        print(f"[tag_pedagogical] failed for {chapter.chapter_id}: {e}")
        return []


async def map_skills_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    results = []
    semaphore = asyncio.Semaphore(3)

    async def process_chapter(chapter: Chapter) -> list:
        async with semaphore:
            for attempt in range(3):
                try:
                    return await _map_skills(chapter)
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            return []

    tasks = [process_chapter(ch) for ch in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    state["skills"] = [r for r in results if isinstance(r, list) and not isinstance(r, Exception)]
    return state


async def _map_skills(chapter: Chapter) -> list:
    from app.kg.agents.skill_mapper import SkillMapper
    from app.kg.src.llm_router import LLMRouter
    try:
        router = LLMRouter()
        mapper = SkillMapper(router.get_client())
        concept_names = [s.title for s in chapter.sections]
        result = mapper.map_skills(concept_names, chapter.content[:500])
        return [r.model_dump() for r in result.q_matrix_entries]
    except Exception as e:
        print(f"[map_skills] failed for {chapter.chapter_id}: {e}")
        return []


def fuse_node(state: PipelineState) -> PipelineState:
    state["resolved_entities"] = []
    return state


def verify_node(state: PipelineState) -> PipelineState:
    return state


def detect_communities_node(state: PipelineState) -> PipelineState:
    state["communities"] = []
    return state


def eval_gate_node(state: PipelineState) -> PipelineState:
    report = state.get("eval_report", {})
    threshold = report.get("threshold", 0.7)
    f1 = report.get("f1", 0.0)

    if f1 >= threshold:
        state["eval_passed"] = True
    else:
        state["eval_passed"] = False

    return state


def eval_fail_report_node(state: PipelineState) -> PipelineState:
    import json
    import pathlib
    import datetime

    report = state.get("eval_report", {})
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    textbook_id = state.get("textbook_id", "unknown")
    out = pathlib.Path(f"eval/baselines/{textbook_id}_fail_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[eval_gate FAILED] report → {out}\n{json.dumps(report, ensure_ascii=False)}")
    return state


def store_node(state: PipelineState) -> PipelineState:
    from app.kg.src.storage.dual_writer import DualWriter
    from app.kg.src.storage.neo4j_writer import Neo4jWriter
    from app.kg.src.storage.qdrant_writer import QdrantWriter
    from app.kg.src.config import get_config
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


def compliance_export_node(state: PipelineState) -> PipelineState:
    return state


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse", parse_node)
    g.add_node("extract_domain", extract_domain_node)
    g.add_node("tag_pedagogical", tag_pedagogical_node)
    g.add_node("map_skills", map_skills_node)
    g.add_node("fuse", fuse_node)
    g.add_node("verify", verify_node)
    g.add_node("detect_communities", detect_communities_node)
    g.add_node("eval_gate", eval_gate_node)
    g.add_node("eval_fail_report", eval_fail_report_node)
    g.add_node("store", store_node)
    g.add_node("compliance_export", compliance_export_node)

    g.set_entry_point("parse")
    g.add_edge("parse", "extract_domain")
    g.add_edge("parse", "tag_pedagogical")
    g.add_edge("parse", "map_skills")
    g.add_edge("extract_domain", "fuse")
    g.add_edge("tag_pedagogical", "fuse")
    g.add_edge("map_skills", "fuse")
    g.add_edge("fuse", "verify")
    g.add_edge("verify", "detect_communities")
    g.add_edge("detect_communities", "eval_gate")
    g.add_conditional_edges(
        "eval_gate",
        lambda s: "store" if s["eval_passed"] else "eval_fail_report"
    )
    g.add_edge("eval_fail_report", END)
    g.add_edge("store", "compliance_export")
    g.add_edge("compliance_export", END)
    return g.compile()


async def run_pipeline(textbook_id: str, chapters: List[Chapter], eval_threshold: float = 0.7) -> PipelineState:
    initial_state: PipelineState = {
        "textbook_id": textbook_id,
        "chapters": chapters,
        "domain_triples": [],
        "pedagogical": [],
        "skills": [],
        "resolved_entities": [],
        "communities": [],
        "eval_passed": False,
        "eval_report": {"threshold": eval_threshold},
    }

    graph = build_graph()
    result = await graph.ainvoke(initial_state)
    return result