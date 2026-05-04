import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rdflib import Graph, RDF, RDFS, OWL
from rdflib.namespace import Namespace


EDUKG = Namespace("http://edukg.org.cn/ontology#")
INSTANCE = Namespace("http://edukg.org.cn/instance#")

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE
)

JYT_EXTENDED_CLASSES = {"CurriculumRequirement"}
JYT_BASE_CLASSES = {"LearningPoint", "EducationalMaterial", "Question", "LearningActivity"}

COGNITIVE_ENUMS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}


def validate_identifier_format(identifier: str) -> bool:
    if not identifier:
        return False
    return bool(UUID_PATTERN.match(identifier))


def validate_json_file(file_path: str) -> Tuple[bool, Optional[str]]:
    try:
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return True, None
        elif isinstance(data, list):
            return True, None
        else:
            return False, "JSON root must be object or array"

    except json.JSONDecodeError as e:
        return False, f"JSON syntax error: {e}"
    except UnicodeDecodeError:
        return False, "File must be UTF-8 encoded"


def validate_rdf_file(file_path: str) -> Tuple[bool, Optional[str]]:
    try:
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        g = Graph()
        g.parse(path, format="turtle")
        return True, None

    except Exception as e:
        return False, f"RDF parsing error: {e}"


def validate_shacl(
    data_path: str,
    shacl_path: str,
    jyt_ontology_path: Optional[str] = None
) -> Tuple[bool, List[str]]:
    errors = []

    if jyt_ontology_path:
        try:
            ont_g = Graph()
            ont_g.parse(jyt_ontology_path, format="turtle")
        except Exception as e:
            errors.append(f"Failed to parse JYT ontology: {e}")
            return False, errors

    try:
        data_g = Graph()
        data_g.parse(data_path, format="turtle")
    except Exception as e:
        errors.append(f"Failed to parse data RDF: {e}")
        return False, errors

    try:
        shacl_g = Graph()
        shacl_g.parse(shacl_path, format="turtle")
    except Exception as e:
        errors.append(f"Failed to parse SHACL shapes: {e}")
        return False, errors

    return True, []


def validate_class_inheritance(entities: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors = []

    for entity in entities:
        entity_type = entity.get("type", "")
        if entity_type == "curriculum_standard_node":
            if "jyt_class" in entity and entity["jyt_class"] != "CurriculumRequirement":
                errors.append(
                    f"Entity {entity.get('id')} has type curriculum_standard_node "
                    f"but jyt_class is {entity.get('jyt_class')}"
                )

    return len(errors) == 0, errors


def validate_extended_properties(entities: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors = []

    for entity in entities:
        entity_type = entity.get("type", "")
        if entity_type == "curriculum_standard_node":
            if "jyt_class" not in entity:
                errors.append(f"Entity {entity.get('id')} missing jyt_class field")
            if "title" not in entity and "name" not in entity:
                errors.append(f"Entity {entity.get('id')} missing title/name field")

    return len(errors) == 0, errors


def validate_required_fields(entities: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors = []

    for entity in entities:
        entity_id = entity.get("id", "")
        if not entity_id:
            errors.append(f"Entity missing id field")
            continue

        if "title" not in entity and "name" not in entity:
            errors.append(f"Entity {entity_id} missing title or name field")

    return len(errors) == 0, errors


def validate_enums(entities: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors = []

    for entity in entities:
        entity_id = entity.get("id", "unknown")
        cognitive = entity.get("cognitive_level")
        if cognitive and cognitive not in COGNITIVE_ENUMS:
            errors.append(
                f"Entity {entity_id} has invalid cognitive_level: {cognitive}"
            )

    return len(errors) == 0, errors


def validate_all(
    entities: List[Dict[str, Any]],
    triples: Optional[List[Dict[str, Any]]] = None,
    check_inheritance: bool = True
) -> Dict[str, Any]:
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
    }

    id_valid, id_errors = validate_identifier_format_list(entities)
    if not id_valid:
        results["valid"] = False
        results["errors"].extend(id_errors)

    req_valid, req_errors = validate_required_fields(entities)
    if not req_valid:
        results["valid"] = False
        results["errors"].extend(req_errors)

    enum_valid, enum_errors = validate_enums(entities)
    if not enum_valid:
        results["valid"] = False
        results["errors"].extend(enum_errors)

    if check_inheritance:
        inh_valid, inh_errors = validate_class_inheritance(entities)
        if not inh_valid:
            results["valid"] = False
            results["errors"].extend(inh_errors)

    return results


def validate_identifier_format_list(
    entities: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    errors = []
    for entity in entities:
        entity_id = entity.get("id", "")
        identifier = entity.get("identifier", entity_id)
        if identifier and not validate_identifier_format(str(identifier)):
            errors.append(
                f"Entity {entity_id} has invalid identifier format: {identifier}"
            )
    return len(errors) == 0, errors