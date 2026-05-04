from typing import Optional, Tuple
from .jyt_0644_codes import INTERNAL_TO_JYT_RELATION


def _map_to_jyt_relation(
    relation_type: str, direction: str = "forward"
) -> Optional[str]:
    key = (relation_type, direction)
    return INTERNAL_TO_JYT_RELATION.get(key)


def get_jyt_relation_uri(relation_name: str) -> str:
    return f"http://edukg.org.cn/ontology#{relation_name}"


def map_triple_to_jyt(
    subject_id: str,
    relation_type: str,
    object_id: str,
    direction: str = "forward"
) -> dict:
    jyt_relation = _map_to_jyt_relation(relation_type, direction)
    if jyt_relation is None:
        return {}

    return {
        "subject": subject_id,
        "relation": relation_type,
        "object": object_id,
        "jyt_relation": jyt_relation,
        "jyt_uri": get_jyt_relation_uri(jyt_relation),
        "direction": direction,
    }


def map_triple_inverse(
    subject_id: str,
    relation_type: str,
    object_id: str
) -> dict:
    return map_triple_to_jyt(subject_id, relation_type, object_id, "backward")


INVERTIBLE_RELATIONS = {"part_of", "skos:broader", "is_a"}


def is_invertible(relation_type: str) -> bool:
    return relation_type in INVERTIBLE_RELATIONS