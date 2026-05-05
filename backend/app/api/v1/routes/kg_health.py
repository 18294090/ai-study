# backend/app/api/v1/routes/kg_health.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.models.user import User
from app.kg.agents.kg_linter import KGLinter
from app.kg.src.storage.neo4j_writer import Neo4jWriter
import os

router = APIRouter()


def get_neo4j_writer() -> Neo4jWriter:
    return Neo4jWriter(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", ""),
    )


@router.get("/kg/health", operation_id="KG健康检查")
async def kg_health_check(
    textbook_id: str = None,
    current_user: User = Depends(get_current_user),
):
    writer = get_neo4j_writer()
    linter = KGLinter(neo4j_driver=writer._driver)
    report = linter.check(textbook_id)
    return {
        "total_nodes": report.total_nodes,
        "total_edges": report.total_edges,
        "health_score": report.health_score,
        "issues_count": len(report.issues),
        "issues": [i.model_dump() for i in report.issues[:20]],
        "checked_at": report.checked_at,
    }


@router.get("/kg/operations", operation_id="查询操作日志")
async def get_operations(
    target_id: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    writer = get_neo4j_writer()
    try:
        with writer._driver.session(database="neo4j") as session:
            if target_id:
                result = session.run(
                    "MATCH (l:OperationLog) WHERE l.target_id = $tid "
                    "RETURN l.timestamp AS ts, l.operation AS op, l.target_id AS tid, "
                    "l.user_id AS uid, l.reasoning AS reason "
                    "ORDER BY ts DESC LIMIT $limit",
                    tid=target_id, limit=limit
                )
            else:
                result = session.run(
                    "MATCH (l:OperationLog) "
                    "RETURN l.timestamp AS ts, l.operation AS op, l.target_id AS tid, "
                    "l.user_id AS uid, l.reasoning AS reason "
                    "ORDER BY ts DESC LIMIT $limit",
                    limit=limit
                )
            logs = []
            for record in result:
                logs.append({
                    "timestamp": str(record["ts"]),
                    "operation": record["op"],
                    "target_id": record["tid"],
                    "user_id": record["uid"],
                    "reasoning": record["reason"],
                })
            return {"operations": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))