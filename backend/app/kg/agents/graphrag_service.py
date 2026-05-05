from __future__ import annotations
from typing import TypedDict, List, Any, Optional
from langgraph.graph import StateGraph, END
import os

from .graphrag.types import (
    Intent, IntentResult, RetrievedChunk, RetrievedEntity,
    Citation, GenerationResult, VerificationResult, GraphRAGResult,
)
from .graphrag.intent_classifier import IntentClassifier
from .graphrag.hybrid_retriever import HybridRetriever
from .graphrag.community_retriever import CommunityRetriever
from .graphrag.reranker import Reranker
from .graphrag.generator import Generator
from .graphrag.verifier import SelfRAGVerifier


class GraphRAGState(TypedDict):
    question: str
    intent: Optional[IntentResult]
    retrieval_type: Optional[str]
    hybrid_results: Optional[Any]
    community_results: Optional[Any]
    reranked_results: Optional[List[Any]]
    generation: Optional[GenerationResult]
    verification: Optional[VerificationResult]
    answer: Optional[str]
    citations: Optional[List[Citation]]
    kg_paths: Optional[List[str]]
    verified: bool
    attempts: int


class GraphRAGService:
    def __init__(
        self,
        neo4j_driver,
        qdrant_client,
        embedder=None,
        api_key: str = None,
    ):
        self.neo4j_driver = neo4j_driver
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

        self.intent_classifier = IntentClassifier(api_key=self.api_key)
        self.hybrid_retriever = HybridRetriever(
            qdrant_client=qdrant_client,
            neo4j_driver=neo4j_driver,
            embedder=embedder,
        )
        self.community_retriever = CommunityRetriever(
            neo4j_driver=neo4j_driver,
            embedder=embedder,
        )
        self.reranker = Reranker(api_key=self.api_key, neo4j_driver=neo4j_driver)
        self.generator = Generator(api_key=self.api_key)
        self.verifier = SelfRAGVerifier(api_key=self.api_key)

    async def query(
        self,
        question: str,
        mode: Optional[str] = None,
        top_k: int = 10,
    ) -> GraphRAGResult:
        state: GraphRAGState = {
            "question": question,
            "intent": None,
            "retrieval_type": None,
            "hybrid_results": None,
            "community_results": None,
            "reranked_results": None,
            "generation": None,
            "verification": None,
            "answer": None,
            "citations": None,
            "kg_paths": None,
            "verified": False,
            "attempts": 0,
        }

        graph = self._build_graph()
        result = await graph.ainvoke(state)

        return GraphRAGResult(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            kg_paths=result.get("kg_paths", []),
            intent=result.get("intent", Intent.FACTUAL) if result.get("intent") else Intent.FACTUAL,
            retrieval_type=result.get("retrieval_type", "hybrid"),
            verification=result.get("verification"),
        )

    def _build_graph(self) -> StateGraph:
        g = StateGraph(GraphRAGState)

        g.add_node("intent", self._intent_node)
        g.add_node("route", self._route_node)
        g.add_node("hybrid_retrieve", self._hybrid_retrieve_node)
        g.add_node("community_retrieve", self._community_retrieve_node)
        g.add_node("rerank", self._rerank_node)
        g.add_node("generate", self._generate_node)
        g.add_node("verify", self._verify_node)

        g.set_entry_point("intent")
        g.add_edge("intent", "route")
        g.add_conditional_edges(
            "route",
            self._route_decision,
            {
                "hybrid": "hybrid_retrieve",
                "community": "community_retrieve",
            }
        )
        g.add_edge("hybrid_retrieve", "rerank")
        g.add_edge("community_retrieve", "rerank")
        g.add_edge("rerank", "generate")
        g.add_edge("generate", "verify")
        g.add_conditional_edges(
            "verify",
            self._verification_decision,
            {
                "pass": END,
                "fail": "generate",
            }
        )
        return g.compile()

    def _intent_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.intent_classifier.classify(state["question"])
        state["intent"] = result
        return state

    def _route_node(self, state: GraphRAGState) -> GraphRAGState:
        return state

    def _route_decision(self, state: GraphRAGState) -> str:
        intent = state.get("intent")
        if intent is None:
            return "hybrid"
        if state["intent"].intent in (Intent.FACTUAL, Intent.PROCEDURAL):
            return "hybrid"
        return "community"

    def _hybrid_retrieve_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.hybrid_retriever.retrieve(state["question"])
        state["hybrid_results"] = result
        state["retrieval_type"] = "hybrid"
        return state

    def _community_retrieve_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.community_retriever.retrieve(state["question"])
        state["community_results"] = result
        state["retrieval_type"] = "community"
        return state

    def _rerank_node(self, state: GraphRAGState) -> GraphRAGState:
        reranked = self.reranker.rerank_hybrid(
            query=state["question"],
            vector_results=state["hybrid_results"].vector_results if state["retrieval_type"] == "hybrid" else [],
            kg_entities=state["hybrid_results"].kg_entities if state["retrieval_type"] == "hybrid" else [],
            top_n=10,
        )
        state["reranked_results"] = reranked
        return state

    def _generate_node(self, state: GraphRAGState) -> GraphRAGState:
        contexts = [r[1] for r in state.get("reranked_results", [])]
        gen_result = self.generator.generate(state["question"], contexts)
        state["generation"] = gen_result
        state["attempts"] = state.get("attempts", 0) + 1
        return state

    def _verify_node(self, state: GraphRAGState) -> GraphRAGState:
        contexts = [r[1] for r in state.get("reranked_results", [])]
        verification = self.verifier.verify(
            state["question"],
            state["generation"],
            contexts,
        )
        state["verification"] = verification
        state["verified"] = verification.is_valid
        if verification.is_valid:
            state["answer"] = state["generation"].answer
            state["citations"] = state["generation"].citations
            state["kg_paths"] = state["generation"].kg_paths
        return state

    def _verification_decision(self, state: GraphRAGState) -> str:
        if state.get("verified", False):
            return "pass"
        if state.get("attempts", 0) >= 2:
            state["answer"] = state["generation"].answer
            state["citations"] = state["generation"].citations
            state["kg_paths"] = state["generation"].kg_paths
            state["verified"] = True
            return "pass"
        return "fail"