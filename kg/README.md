# Knowledge Graph Pipeline

End-to-end pipeline for extracting knowledge graphs from textbooks.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j database URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | (required) | Neo4j password |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector store URL |
| `QDRANT_API_KEY` | (optional) | Qdrant API key |

## Local Development

### Prerequisites

- Python 3.10+
- Neo4j 5.x
- Qdrant 1.x

### Setup

```bash
cd kg
pip install -e .
```

### Environment

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_PASSWORD="your-password"
export QDRANT_URL="http://localhost:6333"
```

## Running the Pipeline

```bash
python run_pipeline.py \
  --input book.pdf --textbook-id math-2026 --subject math \
  --neo4j-uri $NEO4J_URI --qdrant-url $QDRANT_URL \
  --eval-gate strict
```

### Arguments

- `--input`: Path to input PDF file
- `--textbook-id`: Unique textbook identifier (e.g., `math-2026`)
- `--subject`: Subject area (e.g., `math`, `physics`, `chemistry`)
- `--neo4j-uri`: Neo4j connection URI
- `--qdrant-url`: Qdrant vector store URL
- `--eval-gate`: Evaluation threshold mode
  - `strict`: F1 >= 0.8 (default)
  - `relaxed`: F1 >= 0.6
  - `permissive`: F1 >= 0.4

## Evaluation

The pipeline includes an evaluation gate that checks extracted knowledge triples against ground truth annotations.

### Running Evaluation

```bash
python -m pytest tests/test_e2e.py -v
```

### Evaluation Metrics

- **Precision**: Fraction of extracted triples that are correct
- **Recall**: Fraction of ground truth triples that were extracted
- **F1**: Harmonic mean of precision and recall

### Cost Budget

| Operation | Est. Cost (USD) |
|-----------|------------------|
| PDF parsing | $0.02 |
| Domain extraction (per 1K words) | $0.15 |
| Pedagogical tagging (per 1K words) | $0.10 |
| Skill mapping (per 1K words) | $0.10 |
| Eval gate | $0.01 |

**Estimated total**: ~$0.40 per textbook chapter

## Architecture

```
Input PDF
    │
    ▼
┌─────────┐
│  Parse  │
└─────────┘
    │
    ▼
┌──────────────────┐
│ Extract Domain    │
│ Tag Pedagogical   │
│ Map Skills        │
└──────────────────┘
    │
    ▼
┌─────────┐
│  Fuse   │
└─────────┘
    │
    ▼
┌─────────────┐
│   Verify    │
└─────────────┘
    │
    ▼
┌──────────────────┐
│ Detect Communities│
└──────────────────┘
    │
    ▼
┌───────────┐
│ Eval Gate │
└───────────┘
    │
    ▼
┌─────────┐     ┌────────────────┐
│  Store  │────►│ Compliance Exp │
└─────────┘     └────────────────┘
```

## Testing

```bash
python -m pytest tests/ -v
```
