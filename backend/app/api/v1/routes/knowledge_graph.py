from fastapi import APIRouter, Depends
from app.db.neo4j_utils import get_session
from app.core.auth import get_current_user

router = APIRouter()

@router.get("/{subject_id}")
async def get_knowledge_graph(
    subject_id: int,
    current_user = Depends(get_current_user)
):
    """生成知识点关联图谱"""
    with get_session() as session:
        # 获取节点
        nodes_result = session.run("MATCH (kp:KnowledgePoint {subject_id: $subj_id}) RETURN kp.id AS id, kp.name AS name", subj_id=subject_id)
        nodes = [{"id": record["id"], "name": record["name"]} for record in nodes_result]
        
        # 获取关系（假设有 RELATES_TO 关系）
        edges_result = session.run("MATCH (a:KnowledgePoint {subject_id: $subj_id})-[r:RELATES_TO]->(b:KnowledgePoint {subject_id: $subj_id}) RETURN a.id AS source, b.id AS target, r.strength AS strength", subj_id=subject_id)
        edges = [{"source": record["source"], "target": record["target"], "strength": record["strength"]} for record in edges_result]
        
        return {"nodes": nodes, "edges": edges}
        edges = [{"source": record["source"], "target": record["target"], "strength": record["strength"]} for record in edges_result]
        
        # 计算重要性（使用 PageRank）
        pagerank_result = session.run("CALL gds.pageRank.stream('knowledgeGraph') YIELD nodeId, score RETURN nodeId, score")
        centrality = {record["nodeId"]: record["score"] for record in pagerank_result}
        
        # 更新节点重要性
        for node in nodes:
            node["importance"] = centrality.get(node["id"], 0)
        
        return {"nodes": nodes, "edges": edges}
    # 计算中心性和重要程度
    centrality = nx.pagerank(G)
    
    return {
        "nodes": [
            {
                "id": n,
                "name": G.nodes[n]["name"],
                "importance": centrality[n]
            }
            for n in G.nodes()
        ],
        "edges": [
            {
                "source": u,
                "target": v,
                "strength": G.edges[u, v]["weight"]
            }
            for u, v in G.edges()
        ]
    }
