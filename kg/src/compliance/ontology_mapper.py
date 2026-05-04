from typing import Optional
from .jyt_0644_codes import INTERNAL_TO_JYT_CLASS, JYT_CLASSES


def _map_to_jyt_class(entity_type: str) -> Optional[str]:
    return INTERNAL_TO_JYT_CLASS.get(entity_type)


def is_jyt_class(entity_type: str) -> bool:
    return entity_type in JYT_CLASSES


def get_jyt_uri(class_name: str) -> str:
    return f"http://edukg.org.cn/ontology#{class_name}"


def map_entity_to_jyt(entity_type: str, entity_id: str, entity_data: dict) -> dict:
    jyt_class = _map_to_jyt_class(entity_type)
    if jyt_class is None:
        return {}

    result = {
        "id": entity_id,
        "type": entity_type,
        "jyt_class": jyt_class,
        "jyt_uri": get_jyt_uri(jyt_class),
    }

    if "name" in entity_data:
        result["title"] = entity_data["name"]
    elif "title" in entity_data:
        result["title"] = entity_data["title"]

    return result