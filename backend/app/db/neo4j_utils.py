from neo4j import GraphDatabase
from app.core.config import settings
driver = GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
def get_session():
    return driver.session()
def close_driver():
    driver.close()
# 示例：创建知识点
def create_knowledge_point(id, name, description, difficulty, subject_id, creator_id):
    with get_session() as session:
        result = session.run(
            "CREATE (kp:KnowledgePoint {id: $id, name: $name, description: $desc, difficulty: $diff, subject_id: $subj_id, creator_id: $creator_id}) RETURN kp",
            id=id, name=name, desc=description, diff=difficulty, subj_id=subject_id, creator_id=creator_id
        )
        record = result.single()
        return record["kp"] if record else None
# 示例：查询知识点
def get_knowledge_points_by_subject(subject_id):
    with get_session() as session:
        result = session.run("MATCH (kp:KnowledgePoint {subject_id: $subj_id}) RETURN kp", subj_id=subject_id)
        return [record["kp"] for record in result]

# 示例：获取单个知识点
def get_knowledge_point(knowledge_point_id):
    with get_session() as session:
        result = session.run("MATCH (kp:KnowledgePoint {id: $id}) RETURN kp", id=knowledge_point_id)
        record = result.single()
        return record["kp"] if record else None

# 示例：创建知识点关系
def create_knowledge_point_relation(id1, id2, strength=1.0):
    with get_session() as session:
        session.run(
            "MATCH (kp1:KnowledgePoint {id: $id1}), (kp2:KnowledgePoint {id: $id2}) CREATE (kp1)-[:RELATES_TO {strength: $strength}]->(kp2)",
            id1=id1, id2=id2, strength=strength
        )
