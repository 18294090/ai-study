import pytest
from unittest.mock import AsyncMock, patch


def test_kg_gateway_extract_request_model():
    from backend.app.api.v1.routes.kg_gateway import ExtractRequest
    req = ExtractRequest(source="test content", source_type="text")
    assert req.source == "test content"
    assert req.source_type == "text"


def test_kg_gateway_map_relation_request():
    from backend.app.api.v1.routes.kg_gateway import MapRelationRequest
    req = MapRelationRequest(
        source_entity_id="e1",
        target_entity_id="e2",
        relation_type="包含"
    )
    assert req.source_entity_id == "e1"
    assert req.relation_type == "包含"


def test_kg_gateway_detect_conflict_request():
    from backend.app.api.v1.routes.kg_gateway import DetectConflictRequest
    req = DetectConflictRequest(entity_id="123", new_statement="some statement")
    assert req.entity_id == "123"


def test_kg_gateway_verify_request():
    from backend.app.api.v1.routes.kg_gateway import VerifyRequest
    req = VerifyRequest(entity_ids=["e1", "e2"])
    assert len(req.entity_ids) == 2