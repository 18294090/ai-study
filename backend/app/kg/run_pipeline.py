#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_parser import parse_document
from src.models import Textbook, Chapter, Section
from agents.lead_agent import run_pipeline


EVAL_THRESHOLDS = {
    "strict": 0.8,
    "relaxed": 0.6,
    "permissive": 0.4,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Knowledge Graph Pipeline CLI")
    parser.add_argument("--input", required=True, help="Path to input PDF")
    parser.add_argument("--textbook-id", required=True, help="Textbook identifier")
    parser.add_argument("--subject", required=True, help="Subject area")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j URI")
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"), help="Qdrant URL")
    parser.add_argument("--eval-gate", default="strict", choices=["strict", "relaxed", "permissive"], help="Evaluation gate threshold mode")
    parser.add_argument("--edition", default=None, help="Textbook edition")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    return parser.parse_args()


async def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"[pipeline] Starting pipeline for {args.textbook_id}")
    print(f"[pipeline] Input: {input_path}")
    print(f"[pipeline] Subject: {args.subject}")
    print(f"[pipeline] Neo4j: {args.neo4j_uri}")
    print(f"[pipeline] Qdrant: {args.qdrant_url}")
    print(f"[pipeline] Eval gate: {args.eval_gate}")

    try:
        textbook = parse_document(str(input_path))
    except Exception as e:
        print(f"[pipeline] Failed to parse PDF: {e}")
        sys.exit(1)

    textbook.textbook_id = args.textbook_id
    textbook.subject = args.subject
    if args.edition:
        textbook.edition = args.edition

    eval_threshold = EVAL_THRESHOLDS.get(args.eval_gate, 0.8)
    print(f"[pipeline] Running with eval threshold: {eval_threshold}")

    result = await run_pipeline(
        textbook_id=textbook.textbook_id,
        chapters=textbook.chapters,
        eval_threshold=eval_threshold,
    )

    print(f"[pipeline] Pipeline complete")
    print(f"[pipeline] Eval passed: {result.get('eval_passed', False)}")

    eval_report = result.get("eval_report", {})
    if eval_report:
        print(f"[pipeline] F1: {eval_report.get('f1', 'N/A')}")
        print(f"[pipeline] Precision: {eval_report.get('precision', 'N/A')}")
        print(f"[pipeline] Recall: {eval_report.get('recall', 'N/A')}")

    if not result.get("eval_passed", False):
        print("[pipeline] WARNING: eval gate failed, data not stored")
        sys.exit(1)

    print("[pipeline] Done")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
