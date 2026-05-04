import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import Textbook, Chapter, Section
from agents.lead_agent import (
    build_graph,
    PipelineState,
    parse_node,
    extract_domain_node,
    eval_gate_node,
    fuse_node,
    verify_node,
    detect_communities_node,
)
from src.eval.runner import run_eval
from src.eval.metrics import triple_prf, aggregate_metrics


class SmallSampleTextbook:
    @staticmethod
    def create() -> Textbook:
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1: Introduction to Algebra",
                level=1,
                sections=[],
                content="Algebra is a branch of mathematics dealing with symbols and rules for manipulating those symbols.",
                word_count=25,
            ),
            Chapter(
                chapter_id="ch2",
                title="Chapter 2: Linear Equations",
                level=1,
                sections=[],
                content="A linear equation is an equation that describes a straight line. The general form is y = mx + b.",
                word_count=24,
            ),
        ]
        return Textbook(
            textbook_id="math-2026-sample",
            title="Sample Math Textbook",
            subject="math",
            chapters=chapters,
            total_words=49,
        )


class TestE2EComponents:
    def test_parse_node_with_existing_chapters(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": SmallSampleTextbook.create().chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        result = parse_node(state)
        assert result["textbook_id"] == "math-2026-sample"

    @pytest.mark.asyncio
    async def test_extract_domain_processes_chapters(self):
        textbook = SmallSampleTextbook.create()
        state: PipelineState = {
            "textbook_id": textbook.textbook_id,
            "chapters": textbook.chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }

        async def mock_extract(chapter: Chapter) -> list:
            await asyncio.sleep(0.001)
            return [(chapter.chapter_id, "relates_to", "Algebra")]

        with patch("agents.lead_agent._extract_domain_triples", side_effect=mock_extract):
            result = await extract_domain_node(state)
            assert "domain_triples" in result
            assert len(result["domain_triples"]) == 2

    def test_fuse_node_combines_results(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": [],
            "domain_triples": [["A", "rel", "B"]],
            "pedagogical": [["prereq", "X", "Y"]],
            "skills": [["skill", "S1"]],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        result = fuse_node(state)
        assert "resolved_entities" in result

    def test_verify_node_returns_state(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        result = verify_node(state)
        assert result == state

    def test_detect_communities_node_initializes(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        result = detect_communities_node(state)
        assert result["communities"] == []

    def test_eval_gate_passes_high_f1(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.85, "precision": 0.85, "recall": 0.85, "threshold": 0.7},
        }
        result = eval_gate_node(state)
        assert result["eval_passed"] is True

    def test_eval_gate_fails_low_f1(self):
        state: PipelineState = {
            "textbook_id": "math-2026-sample",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.5, "precision": 0.5, "recall": 0.5, "threshold": 0.7},
        }
        result = eval_gate_node(state)
        assert result["eval_passed"] is False


class TestE2EEvalMetrics:
    def test_triple_prf_perfect_match(self):
        pred = [
            {"subject": "A", "predicate": "rel", "object": "B"},
            {"subject": "C", "predicate": "rel", "object": "D"},
        ]
        gold = [
            {"subject": "A", "predicate": "rel", "object": "B"},
            {"subject": "C", "predicate": "rel", "object": "D"},
        ]
        result = triple_prf(pred, gold)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_triple_prf_partial_match(self):
        pred = [{"subject": "A", "predicate": "rel", "object": "B"}]
        gold = [
            {"subject": "A", "predicate": "rel", "object": "B"},
            {"subject": "C", "predicate": "rel", "object": "D"},
        ]
        result = triple_prf(pred, gold)
        assert result["precision"] == 1.0
        assert result["recall"] == 0.5
        assert result["f1"] == pytest.approx(0.666, rel=0.01)

    def test_aggregate_metrics(self):
        results = [
            {"precision": 1.0, "recall": 1.0, "f1": 1.0, "pred_count": 2, "gold_count": 2},
            {"precision": 0.5, "recall": 0.5, "f1": 0.5, "pred_count": 1, "gold_count": 2},
        ]
        agg = aggregate_metrics(results)
        assert "f1" in agg
        assert "precision" in agg
        assert "recall" in agg


class TestE2EGraphStructure:
    def test_graph_compiles_successfully(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_required_nodes(self):
        graph = build_graph()
        nodes = graph.nodes.keys()
        expected = [
            "parse", "extract_domain", "tag_pedagogical", "map_skills",
            "fuse", "verify", "detect_communities", "eval_gate",
            "eval_fail_report", "store", "compliance_export",
        ]
        for node in expected:
            assert node in nodes

    def test_graph_has_conditional_eval_routing(self):
        graph = build_graph()
        assert "eval_gate" in graph.nodes


class TestE2EStateStructure:
    def test_pipeline_state_has_all_required_fields(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        required_fields = [
            "textbook_id", "chapters", "domain_triples", "pedagogical",
            "skills", "resolved_entities", "communities", "eval_passed",
            "eval_report",
        ]
        for field in required_fields:
            assert field in state
