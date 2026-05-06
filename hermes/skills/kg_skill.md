# KG (Knowledge Graph) Skill

## Purpose
Manage knowledge graph construction, querying, and verification using Hermes Agent tools.

## Capabilities
- Extract entities from text/pdf/markdown documents
- Map relations between entities
- Query graph with Cypher, semantic, or hybrid search
- Detect knowledge conflicts
- Verify knowledge correctness

## Tools

### extract_entities
Extract knowledge graph entities from source text or documents.
- Input: source (str), source_type (text|pdf|markdown), subject_id (int, optional)
- Output: entities[], confidence (float)

### map_relations
Create relationships between entities.
- Input: source_entity_id, target_entity_id, relation_type, properties
- Output: relation_id, success

### query_graph
Query the knowledge graph using various methods.
- Input: query (str), query_type (cypher|semantic|hybrid), filters
- Output: results[], paths[], intent

### detect_conflict
Detect conflicts in knowledge graph.
- Input: entity_id, new_statement
- Output: conflicts[], severity

### verify_knowledge
Verify knowledge correctness in the graph.
- Input: entity_ids[]
- Output: verified[], issues[]

## Memory Integration
This skill uses Hermes's persistent memory to:
- Store KG operation history across sessions
- Remember entity disambiguation decisions
- Track relation mapping context
- Maintain verification history

## Configuration
- Neo4j: bolt://localhost:7687, database: neo4j
- Qdrant: http://localhost:6333, collection: textbook_chunks

## Quality Thresholds
- Entity extraction confidence: >= 0.7
- Relation mapping confidence: >= 0.6
- Conflict detection severity threshold: >= 0.5