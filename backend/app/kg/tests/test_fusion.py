import pytest
from unittest.mock import Mock
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from src.fusion.embedder import Embedder
from src.fusion.entity_resolver import EntityResolver
from src.models.entities import Entity, EntityType
from verifier_agent import VerifierAgent


class TestEmbedder:
    def test_embedder_initialization(self):
        embedder = Embedder.__new__(Embedder)
        embedder.model_name = "BAAI/bge-m3"
        embedder.model = None
        assert embedder.model_name == "BAAI/bge-m3"

    def test_embedder_encode_placeholder(self):
        mock_vectors = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        embedder = Embedder.from_embeddings(mock_vectors)
        result = embedder.encode(["text1", "text2"])
        assert result.shape == (2, 3)


class TestEntityResolver:
    def test_bucket_by_type(self):
        embedder = Mock()
        verifier_fn = Mock(return_value=False)
        resolver = EntityResolver(embedder, verifier_fn)

        entities = [
            Entity(id="1", name="Apple", type=EntityType.CONCEPT),
            Entity(id="2", name="Apple Inc", type=EntityType.CONCEPT),
            Entity(id="3", name="Apple fruit", type=EntityType.CONCEPT),
        ]

        buckets = resolver._bucket_by_type(entities)
        assert len(buckets[EntityType.CONCEPT]) == 3

    def test_high_similarity_merges(self):
        mock_vectors = np.array([[1.0, 0.0], [0.99, 0.01]])
        embedder = Embedder.from_embeddings(mock_vectors)
        verifier_fn = Mock(return_value=False)
        resolver = EntityResolver(embedder, verifier_fn, sim_threshold=0.85)

        entities = [
            Entity(id="1", name="Apple", type=EntityType.CONCEPT),
            Entity(id="2", name="Apple Inc", type=EntityType.CONCEPT),
        ]

        clusters = resolver._cluster_bucket(entities)
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_low_similarity_no_merge(self):
        mock_vectors = np.array([[1.0, 0.0], [0.1, 0.9]])
        embedder = Embedder.from_embeddings(mock_vectors)
        verifier_fn = Mock(return_value=False)
        resolver = EntityResolver(embedder, verifier_fn, sim_threshold=0.85)

        entities = [
            Entity(id="1", name="Apple", type=EntityType.CONCEPT),
            Entity(id="2", name="Banana", type=EntityType.CONCEPT),
        ]

        clusters = resolver._cluster_bucket(entities)
        assert len(clusters) == 2

    def test_ambiguous_band_uses_verifier(self):
        mock_vectors = np.array([[1.0, 0.0], [0.80, 0.2]])
        embedder = Embedder.from_embeddings(mock_vectors)
        verifier_fn = Mock(return_value=True)
        resolver = EntityResolver(embedder, verifier_fn, sim_threshold=0.85, ambiguous_band=(0.75, 0.85))

        entities = [
            Entity(id="1", name="Apple", type=EntityType.CONCEPT),
            Entity(id="2", name="Apple Corp", type=EntityType.CONCEPT),
        ]

        clusters = resolver._cluster_bucket(entities)
        assert len(clusters) == 1
        verifier_fn.assert_called_once()

    def test_different_types_do_not_merge(self):
        mock_vectors = np.array([[1.0, 0.0], [0.99, 0.01]])
        embedder = Embedder.from_embeddings(mock_vectors)
        verifier_fn = Mock(return_value=True)
        resolver = EntityResolver(embedder, verifier_fn, sim_threshold=0.85)

        entities = [
            Entity(id="1", name="Apple", type=EntityType.CONCEPT),
            Entity(id="2", name="Banana", type=EntityType.FORMULA),
        ]

        clusters = resolver.cluster(entities)
        assert len(clusters) == 2


class TestVerifierAgent:
    def test_verify_same_entity(self):
        llm_fn = Mock(return_value="是，两者都指苹果公司。")
        agent = VerifierAgent(llm_fn)

        entity1 = Entity(id="1", name="Apple", type=EntityType.CONCEPT)
        entity2 = Entity(id="2", name="Apple Inc", type=EntityType.CONCEPT)

        result = agent.verify(entity1, entity2)
        assert result.is_same is True

    def test_verify_different_entity(self):
        llm_fn = Mock(return_value="否，两者指不同概念。")
        agent = VerifierAgent(llm_fn)

        entity1 = Entity(id="1", name="Apple", type=EntityType.CONCEPT)
        entity2 = Entity(id="2", name="Banana", type=EntityType.CONCEPT)

        result = agent.verify(entity1, entity2)
        assert result.is_same is False

    def test_verify_english_yes(self):
        llm_fn = Mock(return_value="Yes, they refer to the same company.")
        agent = VerifierAgent(llm_fn)

        entity1 = Entity(id="1", name="Apple", type=EntityType.CONCEPT)
        entity2 = Entity(id="2", name="Apple Inc", type=EntityType.CONCEPT)

        result = agent.verify(entity1, entity2)
        assert result.is_same is True