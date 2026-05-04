from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.models import Entity, KnowledgeTriple, EntityType, RelationType, TextbookAnchor
from src.models.triples import _Entity
from src.fusion.embedder import Embedder
from src.storage.neo4j_writer import Neo4jWriter
from src.storage.qdrant_writer import QdrantWriter, QDRANT_AVAILABLE, models
from src.storage.dual_writer import DualWriter, WriteOp


@pytest.fixture
def sample_anchor():
    return TextbookAnchor(
        textbook_id="t1",
        chapter_id="ch1",
        paragraph_offset=10,
        page=42,
    )


@pytest.fixture
def sample_entity(sample_anchor):
    return Entity(
        id="entity1",
        name="Photosynthesis",
        type=EntityType.CONCEPT,
        layer="domain",
        description="Process by which plants convert sunlight to energy",
        anchor=sample_anchor,
        confidence=0.95,
    )


@pytest.fixture
def sample_triple(sample_entity):
    subj = _Entity(
        id="entity2",
        name="Chlorophyll",
        type=EntityType.FORMULA,
        description=None,
        latex=None,
    )
    obj = _Entity(
        id="entity1",
        name="Photosynthesis",
        type=EntityType.CONCEPT,
        description=None,
        latex=None,
    )
    return KnowledgeTriple(
        subject=subj,
        predicate=RelationType.PART_OF,
        object=obj,
        confidence=0.9,
        extracted_by="test_extractor",
    )


class TestNeo4jWriter:
    @pytest.fixture
    def mock_driver(self):
        with patch("src.storage.neo4j_writer.GraphDatabase") as mock_gdb:
            mock_session = MagicMock()
            mock_gdb.driver.return_value.session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_gdb.driver.return_value.session.return_value.__exit__ = Mock(return_value=False)
            mock_gdb.driver.return_value.session.return_value.run.return_value.single.return_value = {"written": 1}
            writer = Neo4jWriter()
            writer._driver = mock_gdb.driver.return_value
            yield writer, mock_session

    def test_entity_labels_with_layer(self, sample_entity):
        with patch("src.storage.neo4j_writer.GraphDatabase"):
            writer = Neo4jWriter()
        labels = writer._entity_labels(sample_entity)
        assert ":concept:" in labels
        assert "domain" in labels

    def test_write_entity(self, mock_driver, sample_entity):
        writer, mock_session = mock_driver
        result = writer.write_entity(sample_entity)
        assert result is True
        mock_session.run.assert_called_once()

    def test_write_entities_batch(self, mock_driver, sample_entity):
        writer, mock_session = mock_driver
        mock_session.run.return_value.single.return_value = {"written": 2}
        entities = [sample_entity, Entity(
            id="entity3",
            name="Cell",
            type=EntityType.CONCEPT,
            layer="domain",
        )]
        count = writer.write_entities_batch(entities)
        assert count == 2

    def test_write_triple(self, mock_driver, sample_triple):
        writer, mock_session = mock_driver
        result = writer.write_triple(sample_triple)
        assert result is True
        assert mock_session.run.called

    def test_write_triples_batch(self, mock_driver, sample_triple):
        writer, mock_session = mock_driver
        mock_session.run.return_value.single.return_value = {"written": 1}
        count = writer.write_triples_batch([sample_triple])
        assert count == 1

    def test_write_community(self, mock_driver):
        writer, mock_session = mock_driver
        result = writer.write_community("comm1", 1, "A summary of the community")
        assert result is True


needs_qdrant = pytest.mark.skipif(not QDRANT_AVAILABLE or models is None, reason="qdrant_client not installed")


@pytest.mark.skipif(not QDRANT_AVAILABLE or models is None, reason="qdrant_client not installed")
class TestQdrantWriter:
    @pytest.fixture
    def mock_embedder(self):
        emb = Embedder.from_embeddings(np.random.rand(5, 1024).astype(np.float32))
        return emb

    @pytest.fixture
    def mock_qdrant_client(self):
        with patch("src.storage.qdrant_writer.QdrantClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_collections.return_value.collections = []
            yield mock_client

    def test_write_node(self, mock_qdrant_client, mock_embedder, sample_entity):
        writer = QdrantWriter(embedder=mock_embedder)
        writer._client = mock_qdrant_client
        result = writer.write_node(sample_entity)
        assert result is True
        mock_qdrant_client.upsert.assert_called_once()

    def test_write_nodes_batch(self, mock_qdrant_client, mock_embedder, sample_entity):
        writer = QdrantWriter(embedder=mock_embedder)
        writer._client = mock_qdrant_client
        entities = [sample_entity, Entity(
            id="entity4",
            name="Mitochondria",
            type=EntityType.CONCEPT,
            layer="domain",
        )]
        count = writer.write_nodes_batch(entities)
        assert count == 2

    def test_write_community_summary(self, mock_qdrant_client, mock_embedder):
        writer = QdrantWriter(embedder=mock_embedder)
        writer._client = mock_qdrant_client
        result = writer.write_community_summary("comm1", 1, "Test summary")
        assert result is True

    def test_write_communities_batch(self, mock_qdrant_client, mock_embedder):
        writer = QdrantWriter(embedder=mock_embedder)
        writer._client = mock_qdrant_client
        communities = [
            {"community_id": "comm1", "level": 1, "summary": "Summary 1"},
            {"community_id": "comm2", "level": 2, "summary": "Summary 2"},
        ]
        count = writer.write_communities_batch(communities)
        assert count == 2


class TestDualWriter:
    @pytest.fixture
    def mock_neo4j(self):
        writer = Mock(spec=Neo4jWriter)
        writer.write_entity.return_value = True
        writer.write_entities_batch.return_value = 2
        writer.write_triple.return_value = True
        writer.write_triples_batch.return_value = 1
        writer.write_community.return_value = True
        writer._driver = MagicMock()
        writer._entity_labels = lambda e: f":{e.type.value}:{e.layer}"
        writer.database = "neo4j"
        return writer

    @pytest.fixture
    def mock_qdrant(self):
        writer = Mock(spec=QdrantWriter)
        writer.write_node.return_value = True
        writer.write_nodes_batch.return_value = 2
        writer.write_community_summary.return_value = True
        return writer

    def test_write_entity_success(self, mock_neo4j, mock_qdrant, sample_entity):
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        result = dual.write_entity(sample_entity)
        assert result is True
        mock_neo4j.write_entity.assert_called_once_with(sample_entity)
        mock_qdrant.write_node.assert_called_once_with(sample_entity)

    def test_write_entity_neo4j_fails(self, mock_neo4j, mock_qdrant, sample_entity):
        mock_neo4j.write_entity.side_effect = Exception("Neo4j error")
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        with pytest.raises(Exception):
            dual.write_entity(sample_entity)
        assert len(dual.get_dead_letters()) == 1
        assert dual.get_dead_letters()[0]["operation"] == WriteOp.ENTITY.value

    def test_write_entity_qdrant_fails_rollback(self, mock_neo4j, mock_qdrant, sample_entity):
        mock_qdrant.write_node.side_effect = Exception("Qdrant error")
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        with pytest.raises(Exception):
            dual.write_entity(sample_entity)
        assert len(dual.get_dead_letters()) == 1
        assert "Qdrant failed after Neo4j success" in dual.get_dead_letters()[0]["error"]

    def test_write_entities_batch(self, mock_neo4j, mock_qdrant, sample_entity):
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        entities = [sample_entity]
        count = dual.write_entities_batch(entities)
        assert count == 2
        mock_neo4j.write_entities_batch.assert_called_once_with(entities)
        mock_qdrant.write_nodes_batch.assert_called_once_with(entities)

    def test_write_triple(self, mock_neo4j, mock_qdrant, sample_triple):
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        result = dual.write_triple(sample_triple)
        assert result is True
        mock_neo4j.write_triple.assert_called_once()
        mock_qdrant.write_node.assert_called()

    def test_write_triples_batch(self, mock_neo4j, mock_qdrant, sample_triple):
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        count = dual.write_triples_batch([sample_triple])
        assert count == 1
        mock_neo4j.write_triples_batch.assert_called_once()
        mock_qdrant.write_nodes_batch.assert_called_once()

    def test_write_community_summary_success(self, mock_neo4j, mock_qdrant):
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        result = dual.write_community_summary("comm1", 1, "Test summary")
        assert result is True
        mock_neo4j.write_community.assert_called_once()
        mock_qdrant.write_community_summary.assert_called_once()

    def test_write_community_summary_qdrant_fails(self, mock_neo4j, mock_qdrant):
        mock_qdrant.write_community_summary.side_effect = Exception("Qdrant error")
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        with pytest.raises(Exception):
            dual.write_community_summary("comm1", 1, "Test summary")
        assert len(dual.get_dead_letters()) == 1
        assert dual.get_dead_letters()[0]["operation"] == WriteOp.COMMUNITY.value

    def test_dead_letter_queue(self, mock_neo4j, mock_qdrant):
        mock_neo4j.write_entity.side_effect = Exception("Neo4j error")
        dual = DualWriter(neo4j=mock_neo4j, qdrant=mock_qdrant)
        entity = Entity(
            id="entity5",
            name="Test",
            type=EntityType.CONCEPT,
            layer="domain",
        )
        try:
            dual.write_entity(entity)
        except Exception:
            pass
        assert len(dual.get_dead_letters()) == 1
        dual.clear_dead_letters()
        assert len(dual.get_dead_letters()) == 0
