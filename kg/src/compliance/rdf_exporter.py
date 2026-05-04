from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL
from typing import List, Dict, Any, Optional
from .ontology_mapper import _map_to_jyt_class, get_jyt_uri
from .relation_mapper import _map_to_jyt_relation, get_jyt_relation_uri

EDUKG = Namespace("http://edukg.org.cn/ontology#")
INSTANCE = Namespace("http://edukg.org.cn/instance#")

JYT_BASE_URI = "http://edukg.org.cn/ontology#"
INSTANCE_BASE_URI = "http://edukg.org.cn/instance#"


def _make_entity_uri(entity_id: str, jyt_class: Optional[str] = None) -> URIRef:
    if jyt_class:
        return INSTANCE[f"{jyt_class}/{entity_id}"]
    return INSTANCE[f"Entity/{entity_id}"]


def _build_entity(g: Graph, entity: Dict[str, Any]) -> None:
    entity_id = entity.get("id")
    if not entity_id:
        return

    entity_type = entity.get("type")
    jyt_class = _map_to_jyt_class(entity_type)

    if jyt_class:
        class_uri = EDUKG[jyt_class]
        entity_uri = _make_entity_uri(entity_id, jyt_class)
        g.add((entity_uri, RDF.type, class_uri))

        title = entity.get("title") or entity.get("name") or entity.get("jyt_class", "")
        if title:
            g.add((entity_uri, RDFS.label, Literal(title)))

        if "subject" in entity and entity["subject"]:
            g.add((entity_uri, EDUKG.subject, Literal(entity["subject"])))

        if "applicable_level" in entity and entity["applicable_level"]:
            g.add((entity_uri, EDUKG.applicableLevel, Literal(entity["applicable_level"])))

        if "cognitive_level" in entity and entity["cognitive_level"]:
            g.add((entity_uri, EDUKG.cognitiveLevel, Literal(entity["cognitive_level"])))

        if "identifier" in entity and entity["identifier"]:
            g.add((entity_uri, EDUKG.identifier, Literal(entity["identifier"])))
        else:
            g.add((entity_uri, EDUKG.identifier, Literal(str(entity_id))))


def _build_triple(g: Graph, triple: Dict[str, Any]) -> None:
    subject_id = triple.get("subject") or triple.get("s")
    relation = triple.get("relation") or triple.get("predicate")
    object_id = triple.get("object") or triple.get("o")

    if not all([subject_id, relation, object_id]):
        return

    jyt_rel = _map_to_jyt_relation(relation, "forward")
    if jyt_rel is None:
        return

    subj_class = triple.get("subject_type")
    obj_class = triple.get("object_type")

    subj_jyt_class = _map_to_jyt_class(subj_class) if subj_class else None
    obj_jyt_class = _map_to_jyt_class(obj_class) if obj_class else None

    subj_uri = _make_entity_uri(str(subject_id), subj_jyt_class)
    obj_uri = _make_entity_uri(str(object_id), obj_jyt_class)
    rel_uri = EDUKG[jyt_rel]

    g.add((subj_uri, rel_uri, obj_uri))


def build_graph(entities: List[Dict[str, Any]], triples: List[Dict[str, Any]]) -> Graph:
    g = Graph()
    g.bind("edukg", EDUKG)
    g.bind("instance", INSTANCE)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("owl", OWL)

    for entity in entities:
        _build_entity(g, entity)

    for triple in triples:
        _build_triple(g, triple)

    return g


def export_to_ttl(g: Graph, output_path: str) -> None:
    g.serialize(destination=output_path, format="turtle")


def export_to_xml(g: Graph, output_path: str) -> None:
    g.serialize(destination=output_path, format="xml")


def export_to_jsonld(g: Graph, output_path: str) -> None:
    g.serialize(destination=output_path, format="json-ld")