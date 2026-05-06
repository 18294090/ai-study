# Phase 1: KG Management → Hermes kg_skill

## 概述

将知识图谱（Knowledge Graph）管理功能从现有 `backend/app/kg/` 模块迁移到 Hermes Agent 的 kg_skill，实现：
- 统一 Agent 框架（Hermes）
- 跨 session 的 KG 操作记忆（Hermes Memory）
- 利用 Hermes 的 MCP 支持进行 FastAPI 与 Hermes 的通信

## 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 迁移范围 | 完整 KG | 所有 KG 功能统一到 Hermes |
| Hermes 部署 | 本地安装 | 通过 curl 安装的 Hermes |
| 通信方式 | MCP Protocol | Hermes 支持 MCP |
| 传输方式 | stdio | 本地进程，低延迟 |

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         FastAPI                              │
│                   (Gateway + BKT/IRT/FSRS)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  MCP Client (app/mcp/hermes_client.py)                       │
│       │                                                      │
│       ▼ stdin/stdout                                        │
│  ┌─────────────────────────────────────────┐                │
│  │         Hermes Agent (本地进程)          │                │
│  │  端口: localhost:8080 (或 stdio)         │                │
│  ├─────────────────────────────────────────┤                │
│  │  Memory (SQLite 三层)                      │                │
│  │  ├── MEMORY.md (短期)                      │                │
│  │  ├── USER.md (用户偏好)                   │                │
│  │  └── sessions/*.db (跨 session)           │                │
│  ├─────────────────────────────────────────┤                │
│  │  Skills:                                  │                │
│  │  ├── kg_skill (NEW)                       │                │
│  │  │   ├── extract_entities_tool            │                │
│  │  │   ├── map_relations_tool                │                │
│  │  │   ├── query_graph_tool                 │                │
│  │  │   ├── detect_conflict_tool             │                │
│  │  │   └── verify_knowledge_tool            │                │
│  │  └── exam_skill (已实现)                  │                │
│  └─────────────────────────────────────────┘                │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────┐                │
│  │         Storage Layer                    │                │
│  │  ├── Neo4j (实体/关系存储)                │                │
│  │  └── Qdrant (向量检索)                   │                │
│  └─────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## KG Skills 工具定义

### extract_entities_tool

```python
{
    "name": "extract_entities",
    "description": "从文本或文档中提取知识图谱实体",
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "文本或文件路径"},
            "source_type": {"type": "string", "enum": ["text", "pdf", "markdown"]},
            "subject_id": {"type": "integer", "description": "学科ID"}
        }
    },
    "output_schema": {
        "entities": [{"id": "str", "name": "str", "type": "str", "properties": {}}],
        "confidence": "float"
    }
}
```

### map_relations_tool

```python
{
    "name": "map_relations",
    "description": "在实体之间建立关系",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_entity_id": {"type": "string"},
            "target_entity_id": {"type": "string"},
            "relation_type": {"type": "string"},
            "properties": {"type": "object"}
        }
    }
}
```

### query_graph_tool

```python
{
    "name": "query_graph",
    "description": "查询知识图谱",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "query_type": {"type": "string", "enum": ["cypher", "semantic", "hybrid"]},
            "filters": {"type": "object"}
        }
    }
}
```

### detect_conflict_tool

```python
{
    "name": "detect_conflict",
    "description": "检测知识冲突",
    "input_schema": {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "new_statement": {"type": "string"}
        }
    }
}
```

### verify_knowledge_tool

```python
{
    "name": "verify_knowledge",
    "description": "验证知识正确性",
    "input_schema": {
        "type": "object",
        "properties": {
            "entity_ids": {"type": "array", "items": {"type": "string"}}
        }
    }
}
```

## FastAPI MCP Client

```python
# app/mcp/hermes_client.py
import asyncio
from typing import Dict, Any, Optional

class HermesMCPClient:
    """MCP client for Hermes Agent communication via stdio."""

    def __init__(self, hermes_path: str = "hermes"):
        self.hermes_path = hermes_path
        self._process: Optional[asyncio.subprocess.Process] = None

    async def start(self):
        """启动 Hermes 进程"""
        self._process = await asyncio.create_subprocess_exec(
            self.hermes_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 Hermes tool"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        await self._process.stdin.send_json(request)
        response = await self._process.stdout.receive_json()
        return response.get("result", {})

    async def call_skill(self, skill_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """调用 Hermes skill"""
        # Skill 调用走不同路径
        ...

    async def stop(self):
        """停止 Hermes 进程"""
        if self._process:
            self._process.terminate()
            await self._process.wait()
```

## API 设计

### 现有 KG Routes 迁移

| 现有 Route | 迁移后 |
|------------|--------|
| `POST /knowledge-extraction/extract` | → Hermes `extract_entities` via MCP |
| `GET /knowledge-points/` | → Hermes `query_graph` via MCP |
| `POST /knowledge-extraction/verify` | → Hermes `verify_knowledge` via MCP |

### 新增 Gateway Routes

```python
# app/api/v1/routes/kg_gateway.py
@router.post("/kg/entities/extract")
async def extract_entities(
    source: str,
    source_type: str = "text",
    subject_id: Optional[int] = None
):
    client = HermesMCPClient()
    result = await client.call_tool("extract_entities", {
        "source": source,
        "source_type": source_type,
        "subject_id": subject_id
    })
    return result

@router.post("/kg/relations/map")
async def map_relations(...):
    ...

@router.get("/kg/query")
async def query_graph(query: str, query_type: str = "hybrid"):
    ...

@router.post("/kg/conflict/detect")
async def detect_conflict(entity_id: str, new_statement: str):
    ...

@router.post("/kg/verify")
async def verify_knowledge(entity_ids: List[str]):
    ...
```

## Hermes Skill 配置

### hermes/skills/kg_skill.md

```markdown
# KG (Knowledge Graph) Skill

## Purpose
管理知识图谱的构建、查询和验证。

## Tools
- extract_entities: 从文本提取实体
- map_relations: 建立实体关系
- query_graph: 查询图谱
- detect_conflict: 冲突检测
- verify_knowledge: 知识验证

## Memory Integration
- 存储 KG 操作历史到 SQLite
- 跨 session 记住实体消歧决策
- 记住关系映射的上下文

## Flow
1. 接收 KG 操作请求
2. 查询 memory 获取历史上下文
3. 调用相应 tool
4. 将结果存入 memory
5. 返回结果

## Neo4j Integration
- 使用 neo4j://localhost:7687
- Database: neo4j

## Qdrant Integration
- URL: http://localhost:6333
- Collection: textbook_chunks
```

## 文件变更

### 新增文件

```
backend/app/mcp/
├── __init__.py
├── hermes_client.py      # MCP client
├── kg_tools.py           # KG tool wrappers
└── config.py             # MCP config

hermes/skills/
└── kg_skill.md           # KG skill 定义

hermes/tools/
└── kg_tools/             # KG tools 实现
    ├── extract_entities.py
    ├── map_relations.py
    ├── query_graph.py
    ├── detect_conflict.py
    └── verify_knowledge.py
```

### 修改文件

```
backend/app/core/config.py      # 添加 hermes client 配置
backend/app/api/v1/__init__.py # 添加 kg_gateway router
backend/app/api/v1/routes/kg_gateway.py  # NEW
```

### 保留文件（不变）

```
backend/app/kg/                  # 保留原实现（可选删除）
backend/app/kg/src/storage/     # 保留 storage 层
```

## 迁移策略

1. **第一阶段：MCP Client**
   - 创建 `app/mcp/hermes_client.py`
   - 测试与本地 Hermes 的通信

2. **第二阶段：KG Tools**
   - 在 Hermes 中实现 5 个 KG tools
   - 配置 hermes/skills/kg_skill.md

3. **第三阶段：Gateway**
   - 创建 `kg_gateway.py` routes
   - FastAPI 调用 MCP client

4. **第四阶段：清理**
   - 移除重复的 KG 代码（如需要）

## 成功标准

1. FastAPI 可以通过 MCP 调用 Hermes kg_skill
2. 所有 5 个 KG tools 可正常工作
3. Hermes Memory 正确记录 KG 操作历史
4. 现有 KG API endpoints 兼容
5. 28 existing tests pass
6. 新增 KG tool tests

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Hermes stdio 通信不稳定 | 添加重试和超时机制 |
| MCP 协议版本不兼容 | 检查 Hermes 版本 (v0.10+) |
| KG 操作性能下降 | 添加缓存和批量处理 |
| Memory 冲突 | 使用 Hermes 的冲突解决机制 |