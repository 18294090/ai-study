import sys
from unittest.mock import MagicMock
import pytest

from src.storage.arbitration_queue import ArbitrationItem
from src.storage.version_tracker import TextbookVersion
from src.storage.incremental_updater import TripleDiff


class TestArbitrationItem:
    def test_create_item(self):
        item = ArbitrationItem(
            source="conflict_detection",
            triple_subj="http://example.org/A",
            triple_pred="http://example.org/B",
            triple_obj="http://example.org/C",
            confidence=0.85,
            context={"reason": "contradiction"},
        )
        assert item.source == "conflict_detection"
        assert item.triple_subj == "http://example.org/A"
        assert item.confidence == 0.85

    def test_item_with_optional_fields_none(self):
        item = ArbitrationItem(
            source="link_prediction",
            triple_subj="S",
            triple_pred="P",
            triple_obj="O",
        )
        assert item.confidence is None
        assert item.context is None


class TestTextbookVersion:
    def test_create_version(self):
        v = TextbookVersion(
            textbook_id="math-2026",
            version="1.0",
            sha256="abc123",
            node_count=100,
            triple_count=500,
        )
        assert v.textbook_id == "math-2026"
        assert v.version == "1.0"
        assert v.sha256 == "abc123"


class TestTripleDiff:
    def test_create_diff(self):
        diff = TripleDiff(op="add", subj="S", pred="P", obj="O")
        assert diff.op == "add"
        assert diff.subj == "S"
        assert diff.pred == "P"
        assert diff.obj == "O"

    def test_diff_operations(self):
        for op in ["add", "remove", "update"]:
            diff = TripleDiff(op=op, subj="S", pred="P", obj="O")
            assert diff.op == op


class TestArbitrationQueueUnit:
    def test_queue_initialization(self):
        from src.storage.arbitration_queue import ArbitrationQueue
        queue = ArbitrationQueue("postgres://test")
        assert queue.conn_str == "postgres://test"


class TestVersionTrackerUnit:
    def test_tracker_initialization(self):
        from src.storage.version_tracker import VersionTracker
        tracker = VersionTracker("postgres://test")
        assert tracker.conn_str == "postgres://test"


class TestIncrementalUpdaterUnit:
    def test_updater_initialization(self):
        from src.storage.incremental_updater import IncrementalUpdater
        mock_driver = MagicMock()
        updater = IncrementalUpdater(mock_driver, "postgres://test")
        assert updater.driver is mock_driver
        assert updater.pg == "postgres://test"