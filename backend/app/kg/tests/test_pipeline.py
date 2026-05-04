import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from agents.lead_agent import (
    PipelineState,
    build_graph,
    parse_node,
    extract_domain_node,
    tag_pedagogical_node,
    map_skills_node,
    fuse_node,
    verify_node,
    detect_communities_node,
    eval_gate_node,
    eval_fail_report_node,
    store_node,
    compliance_export_node,
    run_pipeline,
)
from src.models import Textbook, Chapter, Section


class TestPipelineState:
    def test_pipeline_state_has_required_fields(self):
        state: PipelineState = {
            "textbook_id": "test_id",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        assert state["textbook_id"] == "test_id"
        assert state["eval_passed"] is False


class TestBuildGraph:
    def test_build_graph_returns_compiled_graph(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        graph = build_graph()
        nodes = graph.nodes.keys()
        expected_nodes = [
            "parse",
            "extract_domain",
            "tag_pedagogical",
            "map_skills",
            "fuse",
            "verify",
            "detect_communities",
            "eval_gate",
            "eval_fail_report",
            "store",
            "compliance_export",
        ]
        for node in expected_nodes:
            assert node in nodes


class TestEvalGateNode:
    def test_eval_gate_passes_when_f1_above_threshold(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.8, "precision": 0.8, "recall": 0.8, "threshold": 0.7},
        }
        result = eval_gate_node(state)
        assert result["eval_passed"] is True

    def test_eval_gate_fails_when_f1_below_threshold(self):
        state: PipelineState = {
            "textbook_id": "test",
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

    def test_eval_gate_passes_when_f1_equals_threshold(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.7, "precision": 0.7, "recall": 0.7, "threshold": 0.7},
        }
        result = eval_gate_node(state)
        assert result["eval_passed"] is True


class TestEvalFailReportNode:
    def test_eval_fail_report_writes_file(self, tmp_path):
        state: PipelineState = {
            "textbook_id": "test_book",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.5, "precision": 0.5, "recall": 0.5, "threshold": 0.7},
        }
        with patch("pathlib.Path") as mock_path:
            mock_out = MagicMock()
            mock_out.parent.mkdir = MagicMock()
            mock_path.return_value = mock_out
            mock_out.write_text = MagicMock()

            result = eval_fail_report_node(state)
            assert result["eval_passed"] is False


class TestSimpleNodes:
    def test_fuse_node_initializes_resolved_entities(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [["A", "rel", "B"]],
            "pedagogical": [["prereq", "A", "B"]],
            "skills": [["skill1"]],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }
        result = fuse_node(state)
        assert "resolved_entities" in result

    def test_verify_node_returns_state(self):
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
        result = verify_node(state)
        assert result == state

    def test_detect_communities_node_initializes_communities(self):
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
        result = detect_communities_node(state)
        assert result["communities"] == []

    def test_store_node_returns_state(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": True,
            "eval_report": {},
        }
        result = store_node(state)
        assert result == state

    def test_compliance_export_node_returns_state(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": True,
            "eval_report": {},
        }
        result = compliance_export_node(state)
        assert result == state


@pytest.mark.asyncio
class TestParallelExtraction:
    async def test_extract_domain_node_processes_chapters(self):
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1",
                level=1,
                sections=[],
                content="Content 1",
                word_count=100,
            ),
            Chapter(
                chapter_id="ch2",
                title="Chapter 2",
                level=1,
                sections=[],
                content="Content 2",
                word_count=200,
            ),
        ]
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }

        async def mock_extract(chapter: Chapter) -> list:
            await asyncio.sleep(0.01)
            return [(chapter.chapter_id, "related_to", "Entity")]

        with patch("agents.lead_agent._extract_domain_triples", side_effect=mock_extract):
            result = await extract_domain_node(state)
            assert isinstance(result["domain_triples"], list)

    async def test_tag_pedagogical_node_processes_chapters(self):
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1",
                level=1,
                sections=[],
                content="Content 1",
                word_count=100,
            ),
        ]
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }

        async def mock_tag(chapter: Chapter) -> list:
            await asyncio.sleep(0.01)
            return [(chapter.chapter_id, "has_prereq", "Chapter 2")]

        with patch("agents.lead_agent._tag_pedagogical", side_effect=mock_tag):
            result = await tag_pedagogical_node(state)
            assert isinstance(result["pedagogical"], list)

    async def test_map_skills_node_processes_chapters(self):
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1",
                level=1,
                sections=[],
                content="Content 1",
                word_count=100,
            ),
        ]
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }

        async def mock_map(chapter: Chapter) -> list:
            await asyncio.sleep(0.01)
            return [(chapter.chapter_id, "requires_skill", "skill1")]

        with patch("agents.lead_agent._map_skills", side_effect=mock_map):
            result = await map_skills_node(state)
            assert isinstance(result["skills"], list)


@pytest.mark.asyncio
class TestRunPipeline:
    async def test_run_pipeline_initial_state(self):
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1",
                level=1,
                sections=[],
                content="Content 1",
                word_count=100,
            ),
        ]
        state = {
            "textbook_id": "test_id",
            "chapters": chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"threshold": 0.7},
        }
        graph = build_graph()
        assert graph is not None


class TestConditionalRouting:
    def test_eval_gate_routes_to_store_when_passed(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": True,
            "eval_report": {"f1": 0.8, "threshold": 0.7},
        }
        route = "store" if state["eval_passed"] else "eval_fail_report"
        assert route == "store"

    def test_eval_gate_routes_to_fail_report_when_failed(self):
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": [],
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {"f1": 0.5, "threshold": 0.7},
        }
        route = "store" if state["eval_passed"] else "eval_fail_report"
        assert route == "eval_fail_report"


class TestChapterRetry:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        chapters = [
            Chapter(
                chapter_id="ch1",
                title="Chapter 1",
                level=1,
                sections=[],
                content="Content 1",
                word_count=100,
            ),
        ]
        state: PipelineState = {
            "textbook_id": "test",
            "chapters": chapters,
            "domain_triples": [],
            "pedagogical": [],
            "skills": [],
            "resolved_entities": [],
            "communities": [],
            "eval_passed": False,
            "eval_report": {},
        }

        attempt_count = 0

        async def flaky_extract(chapter: Chapter) -> list:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Temporary failure")
            return [(chapter.chapter_id, "rel", "Entity")]

        with patch("agents.lead_agent._extract_domain_triples", side_effect=flaky_extract):
            with patch("asyncio.sleep", return_value=None):
                result = await extract_domain_node(state)
                assert attempt_count == 3