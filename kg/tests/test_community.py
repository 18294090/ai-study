import sys
from unittest.mock import Mock, MagicMock
import pytest

mock_openai = MagicMock()
mock_anthropic = MagicMock()
sys.modules['openai'] = mock_openai
sys.modules['anthropic'] = mock_anthropic

from agents.community_detector import CommunityDetector, CommunitySummary
from src.routing.structured_client import StructuredClient


class TestCommunityDetector:
    def test_detect_returns_community_stats(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)

        mock_result = MagicMock()
        mock_result.data.return_value = [
            {"c": "C1", "size": 150},
            {"c": "C2", "size": 80},
            {"c": "C3", "size": 25},
        ]
        mock_session.run.return_value = mock_result

        mock_client = MagicMock(spec=StructuredClient)
        detector = CommunityDetector(mock_driver, mock_client)

        result = detector.detect()

        assert len(result) == 3
        assert result[0]["c"] == "C1"
        assert result[0]["size"] == 150

    def test_summarize_generates_community_summary(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)

        run_call_count = [0]
        def run_effect(*args, **kwargs):
            run_call_count[0] += 1
            mock_result = MagicMock()
            if run_call_count[0] == 1:
                mock_result.data.return_value = [
                    {"node_id": 1, "labels": ["Concept"], "name": "Machine Learning"},
                    {"node_id": 2, "labels": ["Concept"], "name": "Neural Network"},
                ]
            else:
                mock_result.data.return_value = [
                    {"from": "Machine Learning", "rel_type": "SUBSUMES", "to": "Neural Network"},
                ]
            return mock_result

        mock_session.run.side_effect = run_effect

        mock_client = MagicMock(spec=StructuredClient)
        mock_client.extract.return_value = CommunitySummary(
            level=0,
            community_id="C1",
            core_concepts=["Machine Learning", "Neural Network"],
            key_relationships=["Machine Learning SUBSUMES Neural Network"],
            typical_applications=["Deep Learning", "AI"],
            summary_text="A community about ML concepts",
        )

        detector = CommunityDetector(mock_driver, mock_client)

        result = detector.summarize("C1", level=0)

        assert isinstance(result, CommunitySummary)
        assert result.community_id == "C1"
        assert len(result.core_concepts) == 2
        assert "Machine Learning" in result.core_concepts

    def test_detect_and_summarize_workflow(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)

        run_call_count = [0]
        def run_effect(*args, **kwargs):
            run_call_count[0] += 1
            if run_call_count[0] == 3:
                mock_result = MagicMock()
                mock_result.data.return_value = [{"c": "C1", "size": 100}]
                return mock_result
            elif run_call_count[0] == 4:
                mock_result = MagicMock()
                mock_result.data.return_value = [{"node_id": 1, "labels": ["Concept"], "name": "Test"}]
                return mock_result
            elif run_call_count[0] == 5:
                mock_result = MagicMock()
                mock_result.data.return_value = []
                return mock_result
            return MagicMock()

        mock_session.run.side_effect = run_effect

        mock_client = MagicMock(spec=StructuredClient)
        mock_client.extract.return_value = CommunitySummary(
            level=0,
            community_id="C1",
            core_concepts=["Test"],
            key_relationships=[],
            typical_applications=["Testing"],
            summary_text="Test community",
        )

        detector = CommunityDetector(mock_driver, mock_client)
        summaries = detector.detect_and_summarize()

        assert len(summaries) == 1
        assert summaries[0].community_id == "C1"


class TestCommunitySummarySchema:
    def test_community_summary_has_required_fields(self):
        summary = CommunitySummary(
            level=1,
            community_id="C0",
            core_concepts=["Concept A", "Concept B"],
            key_relationships=["A relates to B"],
            typical_applications=["Application 1"],
            summary_text="Summary of community",
        )

        assert summary.level == 1
        assert summary.community_id == "C0"
        assert len(summary.core_concepts) == 2
        assert len(summary.key_relationships) == 1
        assert len(summary.typical_applications) == 1

    def test_community_summary_optional_fields(self):
        summary = CommunitySummary(
            level=0,
            community_id="C0",
            core_concepts=[],
            key_relationships=[],
            typical_applications=[],
            summary_text="Empty community",
        )

        assert summary.level == 0
        assert summary.core_concepts == []
