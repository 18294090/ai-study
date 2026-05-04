import re
from typing import List, Dict, Set, Tuple

SYNONYMS = {
    "三角形": ["三角", "三角形的"],
    "几何图形": ["几何形状", "图形"],
    "顶点": ["角", "尖点"],
    "边": ["边长", "线条"],
    "氢原子": ["氢"],
    "氧原子": ["氧"],
    "元素": ["化学元素"],
    "光合作用": ["光合"],
    "葡萄糖": ["糖", "单糖"],
    "蛋白质": ["蛋白"],
}


def normalize(text: str) -> str:
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[，。、；：''""（）《》【】]', '', text)
    return text.lower()


def are_synonyms(a: str, b: str) -> bool:
    norm_a = normalize(a)
    norm_b = normalize(b)
    if norm_a == norm_b:
        return True
    if norm_a in SYNONYMS:
        if norm_b in SYNONYMS[norm_a]:
            return True
    if norm_b in SYNONYMS:
        if norm_a in SYNONYMS[norm_b]:
            return True
    return False


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