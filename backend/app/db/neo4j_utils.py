from neo4j import GraphDatabase
from app.core.config import settings

driver = GraphDatabase.driver(
    settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)


def get_session():
    return driver.session()


def close_driver():
    driver.close()


# 创建知识点（节点）
def create_knowledge_point(
    id: int,
    name: str,
    description: str | None,
    difficulty: int | None,
    subject_id: int,
    creator_id: int,
    code: str | None = None,
    slug: str | None = None,
):
    with get_session() as session:
        result = session.run(
            """
            MERGE (kp:KnowledgePoint {id: $id})
            ON CREATE SET kp.name = $name,
                          kp.description = $desc,
                          kp.difficulty = coalesce($diff, 3),
                          kp.subject_id = $subj_id,
                          kp.creator_id = $creator_id,
                          kp.code = $code,
                          kp.slug = $slug
            ON MATCH SET kp.name = $name,
                         kp.description = $desc,
                         kp.difficulty = coalesce($diff, kp.difficulty),
                         kp.code = coalesce($code, kp.code),
                         kp.slug = coalesce($slug, kp.slug)
            RETURN kp
            """,
            id=id,
            name=name,
            desc=description,
            diff=difficulty,
            subj_id=subject_id,
            creator_id=creator_id,
            code=code,
            slug=slug,
        )
        record = result.single()
        return record["kp"] if record else None
# 查询：按学科ID
def get_knowledge_points_by_subject(subject_id: int):
    with get_session() as session:
        result = session.run(
            "MATCH (kp:KnowledgePoint {subject_id: $subj_id}) RETURN kp ORDER BY coalesce(kp.name,'')",
            subj_id=subject_id,
        )
        return [record["kp"] for record in result]


# 查询：单个节点
def get_knowledge_point(knowledge_point_id: int):
    with get_session() as session:
        result = session.run("MATCH (kp:KnowledgePoint {id: $id}) RETURN kp", id=knowledge_point_id)
        record = result.single()
        return record["kp"] if record else None

# 模糊搜索（按名称/描述）
def search_knowledge_points(subject_id: int, q: str):
    with get_session() as session:
        # 使用 toLower 简单模糊匹配（生产可用 ES）
        result = session.run(
            """
            MATCH (kp:KnowledgePoint {subject_id: $subj_id})
            WHERE toLower(kp.name) CONTAINS toLower($q)
               OR toLower(coalesce(kp.description,'')) CONTAINS toLower($q)
            RETURN kp
            ORDER BY coalesce(kp.name,'')
            LIMIT 100
            """,
            subj_id=subject_id, q=q,
        )
        return [record["kp"] for record in result]
    
ALLOWED_REL_TYPES = {
    "RELATES_TO",
    "CONTAINS",
    "COMPOSED_OF",
    "PREREQUISITE",
    "DEPENDS_ON",
    "APPLIES_TO",
    "APPLIED_BY",
    "RELATED_TO",
    "SIMILAR_TO",
    "THEORY_SUPPORTS",
    "METHOD_BORROWS",
    "CROSS_DISCIPLINE",
}

def _validate_rel_type(rel_type: str) -> str:
    rt = rel_type.strip().upper()
    if rt not in ALLOWED_REL_TYPES:
        raise ValueError(f"Unsupported relationship type: {rel_type}")
    return rt

def would_create_cycle(source_id: int, target_id: int, rel_type: str) -> bool:
    """检测添加某类型关系是否会在同类型边上形成环（例如 CONTAINS、PREREQUISITE 等）。"""
    rt = _validate_rel_type(rel_type)
    with get_session() as session:
        # 检测从目标到源是否已存在路径（同类型边），若存在则加边会形成环
        query = f"""
        MATCH (a:KnowledgePoint {{id: $target}}), (b:KnowledgePoint {{id: $source}})
        MATCH p = (a)-[:{rt}*]->(b)
        RETURN count(p) > 0 AS has_path
        """
        rec = session.run(query, source=source_id, target=target_id).single()
        return bool(rec and rec.get("has_path"))

def create_knowledge_point_relation(id1: int, id2: int, strength: float = 1.0):
    """保持兼容：默认RELATES_TO类型。"""
    return create_typed_relation(id1, id2, rel_type="RELATES_TO", strength=strength)


def create_typed_relation(id1: int, id2: int, rel_type: str, strength: float = 1.0):
    rt = _validate_rel_type(rel_type)
    with get_session() as session:
        # 防环（仅对层次/依赖类关系更常见，全部类型统一防御）
        if would_create_cycle(id1, id2, rt):
            raise ValueError("Creating this relationship would introduce a cycle")
        query = f"""
        MATCH (kp1:KnowledgePoint {{id: $id1}}), (kp2:KnowledgePoint {{id: $id2}})
        MERGE (kp1)-[r:{rt}]->(kp2)
        ON CREATE SET r.strength = $strength
        ON MATCH SET r.strength = coalesce(r.strength, $strength)
        RETURN r
        """
        session.run(query, id1=id1, id2=id2, strength=strength)
