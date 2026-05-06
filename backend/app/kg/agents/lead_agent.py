from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Any, Optional
import asyncio
from app.kg.src.models import Textbook, Chapter
from app.kg.src.logger import get_logger

logger = get_logger("lead_agent")


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
    contradictions: list


def parse_node(state: PipelineState) -> PipelineState:
    if not state.get("chapters"):
        raise ValueError("parse_node requires chapters in state")
    return state


async def bounded_retry_gather(
    items: list,
    worker_fn,
    concurrency: int = 3,
    max_retries: int = 3,
) -> list:
    """Run ``worker_fn(item)`` for every item with bounded concurrency and
    exponential-backoff retries.  Returns a flat list of non-exception results.

    This replaces the three identical semaphore+retry patterns that used to live
    inside extract_domain_node / tag_pedagogical_node / map_skills_node.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(item) -> Any:
        async with semaphore:
            last_error: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    coro = worker_fn(item)
                    return await coro if asyncio.iscoroutine(coro) else coro
                except Exception as exc:
                    last_error = exc
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            raise last_error  # type: ignore[misc]

    raw = await asyncio.gather(*[_run(it) for it in items], return_exceptions=True)
    return [r for r in raw if not isinstance(r, BaseException)]


async def extract_domain_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    state["domain_triples"] = await bounded_retry_gather(chapters, _extract_domain_triples)
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
        logger.warning(f"extract_domain failed for {chapter.chapter_id}: {e}")
        return []


async def tag_pedagogical_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    state["pedagogical"] = await bounded_retry_gather(chapters, _tag_pedagogical)
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
        logger.warning(f"tag_pedagogical failed for {chapter.chapter_id}: {e}")
        return []


async def map_skills_node(state: PipelineState) -> PipelineState:
    chapters = state.get("chapters", [])
    state["skills"] = await bounded_retry_gather(chapters, _map_skills)
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
        logger.warning(f"map_skills failed for {chapter.chapter_id}: {e}")
        return []


def fuse_node(state: PipelineState) -> PipelineState:
    triples = state.get("domain_triples", [])
    resolved = []
    seen = set()

    for t in triples:
        key = (
            t.get("subject", ""),
            t.get("predicate", ""),
            t.get("object", "")
        )
        if key not in seen:
            seen.add(key)
            resolved.append(t)

    state["resolved_entities"] = resolved
    return state


def check_contradictions_node(state: PipelineState) -> PipelineState:
    from app.kg.agents.contradiction_detector import ContradictionDetector
    from app.kg.src.storage.neo4j_writer import Neo4jWriter
    from app.kg.src.config import get_config
    import os

    cfg = get_config()
    neo4j_cfg = cfg.storage.get("neo4j", {})
    neo4j_driver = Neo4jWriter(
        uri=os.environ.get(neo4j_cfg.get("uri_env", "NEO4J_URI"), "bolt://localhost:7687"),
        user=os.environ.get(neo4j_cfg.get("user_env", "NEO4J_USER"), "neo4j"),
        password=os.environ.get(neo4j_cfg.get("password_env", "NEO4J_PASSWORD"), ""),
    )

    triples = state.get("domain_triples", [])
    if not triples:
        return state

    textbook_id = state.get("textbook_id", "")
    detector = ContradictionDetector(neo4j_driver=neo4j_driver._driver)
    contradictions = detector.detect(triples, textbook_id)

    high_severity = [c for c in contradictions if c.severity >= 0.5]
    if high_severity:
        logger.info(f"{len(high_severity)} contradictions flagged for review")

    state["contradictions"] = [c.model_dump() for c in contradictions]
    return state


def verify_node(state: PipelineState) -> PipelineState:
    verified_count = len(state.get("domain_triples", []))
    logger.debug(f"verified {verified_count} triples")
    return state


def detect_communities_node(state: PipelineState) -> PipelineState:
    from app.kg.agents.community_detector import CommunityDetector
    from app.kg.src.storage.neo4j_writer import Neo4jWriter
    from app.kg.src.config import get_config
    import os

    cfg = get_config()
    neo4j_cfg = cfg.storage.get("neo4j", {})
    neo4j_driver = Neo4jWriter(
        uri=os.environ.get(neo4j_cfg.get("uri_env", "NEO4J_URI"), "bolt://localhost:7687"),
        user=os.environ.get(neo4j_cfg.get("user_env", "NEO4J_USER"), "neo4j"),
        password=os.environ.get(neo4j_cfg.get("password_env", "NEO4J_PASSWORD"), ""),
    )

    detector = CommunityDetector(neo4j_driver._driver, None)
    try:
        communities = detector.detect()
        state["communities"] = communities
        logger.info(f"found {len(communities)} communities")
    except Exception as e:
        logger.error(f"detect_communities failed: {e}")
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
    logger.warning(f"eval FAILED, report → {out}")
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
            logger.error(f"triple write failed: {e}")

    return state


def compliance_export_node(state: PipelineState) -> PipelineState:
    import json
    import pathlib

    textbook_id = state.get("textbook_id", "unknown")
    out = pathlib.Path(f"eval/compliance/{textbook_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    export_data = {
        "textbook_id": textbook_id,
        "domain_triples": state.get("domain_triples", []),
        "pedagogical": state.get("pedagogical", []),
        "skills": state.get("skills", []),
        "communities": state.get("communities", []),
        "eval_passed": state.get("eval_passed", False),
    }

    out.write_text(json.dumps(export_data, ensure_ascii=False, indent=2))
    logger.info(f"exported to {out}")
    return state


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse", parse_node)
    g.add_node("extract_domain", extract_domain_node)
    g.add_node("tag_pedagogical", tag_pedagogical_node)
    g.add_node("map_skills", map_skills_node)
    g.add_node("fuse", fuse_node)
    g.add_node("check_contradictions", check_contradictions_node)
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
    g.add_edge("extract_domain", "check_contradictions")
    g.add_edge("tag_pedagogical", "check_contradictions")
    g.add_edge("map_skills", "check_contradictions")
    g.add_edge("check_contradictions", "fuse")
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