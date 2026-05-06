from neo4j import Driver
from pydantic import BaseModel
from typing import List, Optional
from ..src.routing.structured_client import StructuredClient


class CommunitySummary(BaseModel):
    level: int
    community_id: str
    core_concepts: List[str]
    key_relationships: List[str]
    typical_applications: List[str]
    summary_text: str


class CommunityDetector:
    def __init__(self, neo4j_driver: Driver, summary_client: StructuredClient):
        self.driver = neo4j_driver
        self.summary_client = summary_client

    def detect(self, database: str = "neo4j") -> List[dict]:
        with self.driver.session(database=database) as s:
            # Idempotent projection: drop if stale, then recreate.
            exists_result = s.run("CALL gds.graph.exists('kg') YIELD exists").single()
            if exists_result and exists_result["exists"]:
                s.run("CALL gds.graph.drop('kg', false) YIELD graphName")
            s.run("CALL gds.graph.project('kg', '*', '*')")
            s.run("""CALL gds.leiden.write('kg',
                {writeProperty: 'community_id', includeIntermediateCommunities: true})""")
            # Always drop the in-memory projection after use to free GDS memory.
            s.run("CALL gds.graph.drop('kg', false) YIELD graphName")
            result = s.run(
                "MATCH (n) WHERE n.community_id IS NOT NULL "
                "RETURN n.community_id AS c, count(*) AS size "
                "ORDER BY size DESC"
            ).data()
            return result

    def summarize(self, community_id: str, level: int, database: str = "neo4j") -> CommunitySummary:
        with self.driver.session(database=database) as s:
            nodes_data = s.run(
                "MATCH (n) WHERE n.community_id = $community_id "
                "RETURN n.id AS node_id, labels(n) AS labels, n.name AS name",
                community_id=community_id,
            ).data()

            rels_data = s.run(
                "MATCH (a)-[r]->(b) "
                "WHERE a.community_id = $community_id AND b.community_id = $community_id "
                "RETURN a.name AS from, type(r) AS rel_type, b.name AS to",
                community_id=community_id,
            ).data()

        nodes_text = "\n".join(
            f"- {n['labels'][0]}: {n['name']}" for n in nodes_data if n.get("name")
        )
        rels_text = "\n".join(
            f"- {r['from']} --[{r['rel_type']}]--> {r['to']}" for r in rels_data
        )

        user_prompt = f"""社区 {community_id} (层级 {level}) 包含 {len(nodes_data)} 个节点:

节点:
{nodes_text}

关系:
{rels_text}

请生成该社区的结构化摘要，包含核心概念、关键关系、典型应用。"""

        system_prompt = """You are a knowledge graph analyst. Generate a hierarchical community summary.
Output JSON with: level, community_id, core_concepts (list), key_relationships (list), typical_applications (list), summary_text."""

        return self.summary_client.extract(
            system=system_prompt,
            user=user_prompt,
            schema=CommunitySummary,
        )

    def detect_and_summarize(self, database: str = "neo4j") -> List[CommunitySummary]:
        communities = self.detect(database)
        summaries = []
        for comm in communities:
            c_id = comm["c"]
            level = 0
            summary = self.summarize(c_id, level, database)
            summaries.append(summary)
        return summaries
