import json
import hashlib
from pathlib import Path
from typing import List, Dict, Callable, Any

from .metrics import triple_prf, aggregate_metrics


def load_dataset(dataset_path: str) -> List[Dict]:
    data = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def run_eval(
    extractor: Callable[[str], List[Dict]],
    dataset_path: str,
    output_dir: str = "eval/baselines",
) -> Dict[str, Any]:
    dataset = load_dataset(dataset_path)

    results = []
    for item in dataset:
        chapter_text = item.get("chapter_text", "")
        expected = item.get("expected_triples", [])

        pred_triples = extractor(chapter_text)

        prf = triple_prf(pred_triples, expected)
        results.append({
            "chapter_text": chapter_text[:50],
            "precision": prf["precision"],
            "recall": prf["recall"],
            "f1": prf["f1"],
            "pred_count": len(pred_triples),
            "gold_count": len(expected),
        })

    agg = aggregate_metrics(results)

    sha = hashlib.md5(dataset_path.encode()).hexdigest()[:8]
    output_path = Path(output_dir) / f"{sha}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "dataset": dataset_path,
        "timestamp": str(Path(dataset_path).stat().st_mtime),
        "sample_count": len(dataset),
        "metrics": agg,
        "details": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return {
        "metrics": agg,
        "results": results,
        "output_path": str(output_path),
        "sample_count": len(dataset),
    }


def compare_with_baseline(current: Dict, baseline_path: str) -> Dict[str, Any]:
    if not Path(baseline_path).exists():
        return {"has_baseline": False}

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    baseline_f1 = baseline.get("metrics", {}).get("f1", 0.0)
    current_f1 = current.get("metrics", {}).get("f1", 0.0)

    return {
        "has_baseline": True,
        "baseline_f1": baseline_f1,
        "current_f1": current_f1,
        "delta": round(current_f1 - baseline_f1, 4),
    }