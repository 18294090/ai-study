import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Dynamic synonym registry — use register_synonyms() to add domain-specific
# entries at runtime (e.g. from curriculum ontology lookups) instead of
# embedding a fixed vocabulary here.
# ---------------------------------------------------------------------------
_SYNONYM_MAP: Dict[str, Set[str]] = {}


def register_synonyms(canonical: str, aliases: List[str]) -> None:
    """Register ``aliases`` as synonyms of ``canonical`` (bidirectional)."""
    key = canonical.lower()
    _SYNONYM_MAP.setdefault(key, set()).update(a.lower() for a in aliases)
    for alias in aliases:
        _SYNONYM_MAP.setdefault(alias.lower(), set()).add(key)


# Seed with a small starter set; callers should extend via register_synonyms()
_STARTER: List[tuple] = [
    ("三角形", ["三角", "三角形的"]),
    ("几何图形", ["几何形状", "图形"]),
    ("顶点", ["尖点"]),
    ("氢原子", ["氢"]),
    ("氧原子", ["氧"]),
    ("元素", ["化学元素"]),
    ("光合作用", ["光合"]),
    ("葡萄糖", ["单糖"]),
    ("蛋白质", ["蛋白"]),
]
for _canon, _aliases in _STARTER:
    register_synonyms(_canon, _aliases)

# ---------------------------------------------------------------------------
# Similarity thresholds
# ---------------------------------------------------------------------------
# Sequence-similarity threshold for accepting two tokens as synonyms when no
# embedding model is available.  0.82 works well for Chinese domain terms.
_EDIT_SIM_THRESHOLD = 0.82

# Optional embedding-based similarity (used when FlagEmbedding is installed).
_embedder = None  # lazily initialised


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore
        _embedder = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    except Exception:
        pass
    return _embedder


def _cosine_sim(a: str, b: str) -> Optional[float]:
    """Return cosine similarity using BGE-M3, or None if unavailable."""
    emb = _get_embedder()
    if emb is None:
        return None
    try:
        import numpy as np
        vecs = emb.encode([a, b])["dense_vecs"]
        va, vb = vecs[0], vecs[1]
        denom = (np.linalg.norm(va) * np.linalg.norm(vb))
        return float(np.dot(va, vb) / denom) if denom > 0 else 0.0
    except Exception:
        return None


def normalize(text: str) -> str:
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[，。、；：\u2018\u2019\u201c\u201d（）《》【】]', '', text)
    return text.lower()


def are_synonyms(a: str, b: str) -> bool:
    norm_a = normalize(a)
    norm_b = normalize(b)
    if norm_a == norm_b:
        return True

    # Registry lookup (O(1))
    if norm_b in _SYNONYM_MAP.get(norm_a, set()):
        return True
    if norm_a in _SYNONYM_MAP.get(norm_b, set()):
        return True

    # Embedding-based cosine similarity (high precision, optional)
    cos = _cosine_sim(norm_a, norm_b)
    if cos is not None:
        return cos >= 0.88  # tight threshold to avoid false positives

    # Fallback: edit-distance similarity (language-agnostic)
    sim = SequenceMatcher(None, norm_a, norm_b).ratio()
    return sim >= _EDIT_SIM_THRESHOLD


def match_entity(entity: str, candidates: List[str]) -> str | None:
    norm_entity = normalize(entity)
    for cand in candidates:
        if are_synonyms(entity, cand) or norm_entity in normalize(cand) or normalize(cand) in norm_entity:
            return cand
    return None


def triple_prf(pred: List[Dict], gold: List[Dict]) -> Dict[str, float]:
    if not gold:
        return {"precision": 1.0 if not pred else 0.0, "recall": 1.0, "f1": 1.0 if not pred else 0.0}

    if not pred:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0}

    pred_matched = 0
    gold_matched_mask = [False] * len(gold)

    for p_triple in pred:
        p_subj = p_triple.get("subject", "")
        p_pred = p_triple.get("predicate", "")
        p_obj = p_triple.get("object", "")

        for i, g_triple in enumerate(gold):
            if gold_matched_mask[i]:
                continue

            g_subj = g_triple.get("subject", "")
            g_pred = g_triple.get("predicate", "")
            g_obj = g_triple.get("object", "")

            subj_match = are_synonyms(p_subj, g_subj)
            pred_match = are_synonyms(p_pred, g_pred) or normalize(p_pred) == normalize(g_pred)
            obj_match = are_synonyms(p_obj, g_obj)

            if subj_match and pred_match and obj_match:
                pred_matched += 1
                gold_matched_mask[i] = True
                break

    precision = pred_matched / len(pred) if pred else 0.0
    recall = sum(gold_matched_mask) / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def aggregate_metrics(results: List[Dict]) -> Dict[str, float]:
    if not results:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    total_precision = sum(r["precision"] for r in results)
    total_recall = sum(r["recall"] for r in results)
    total_f1 = sum(r["f1"] for r in results)

    n = len(results)

    return {
        "precision": round(total_precision / n, 4),
        "recall": round(total_recall / n, 4),
        "f1": round(total_f1 / n, 4),
    }