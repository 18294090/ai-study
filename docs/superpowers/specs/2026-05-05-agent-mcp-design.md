# Agent MCP Interface & Audit System Design

## 1. Overview

### Goals
- Expose all REST APIs as MCP tools for Agent consumption
- Implement full audit logging for all agent operations
- Support multi-step undo capability

### Architecture
```
Agent (MCP Client)
    ↓
/mcp (FastApiMCP)
    ↓
MCP Tool Adapter Layer
    ├── kg_read tools     → GraphRAG retrieval
    ├── kg_write tools    → KG CRUD + conflict detection
    ├── mastery tools     → BKT updates
    ├── tutor tools       → Socratic tutor
    ├── irt tools         → IRT calibration
    ├── fsrs tools        → Spaced repetition
    └── expert tools      → Conflict resolution
    ↓
Audit Log Middleware (tracks all operations)
    ↓
Services + Database
```

---

## 2. MCP Tool Interface

### 2.1 Tool Naming Convention

All tools follow: `{module}_{operation}`
- `kg_query` - Query knowledge graph
- `kg_create_entity` - Create entity
- `kg_update_entity` - Update entity
- `kg_delete_entity` - Delete entity
- `kg_create_relation` - Create relation
- `mastery_update` - Update mastery
- `mastery_diagnose` - Run diagnostic
- `tutor_start_session` - Start tutor session
- `tutor_message` - Send tutor message
- `irt_calibrate` - Calibrate items
- `irt_estimate_ability` - Estimate ability
- `fsrs_create_card` - Create FSRS card
- `fsrs_review` - Submit review
- `fsrs_get_due` - Get due cards
- `expert_get_conflicts` - Get conflict queue
- `expert_resolve` - Resolve conflict
- `undo` - Undo operations

### 2.2 Standard Tool Parameters

Every tool accepts:
- `agent_id: str` - Identifier for the agent
- `session_id: str` - Session identifier for grouping related operations

### 2.3 Tool Response Format

```python
class ToolResponse(BaseModel):
    success: bool
    data: Optional[dict]
    error: Optional[str]
    operation_id: str  # For tracking/undo
    timestamp: datetime
```

---

## 3. Audit Log System

### 3.1 AgentOperationLog Model

```python
class AgentOperationLog(Base):
    __tablename__ = "agent_operation_logs"

    id: int = Column(Integer, primary_key=True)
    agent_id: str = Column(String, nullable=False, index=True)
    session_id: str = Column(String, nullable=False, index=True)
    operation: str = Column(String, nullable=False)
    tool_name: str = Column(String, nullable=False)
    entity_type: str = Column(String, nullable=True)
    entity_id: str = Column(String, nullable=True)
    before_state: dict = Column(JSON, nullable=True)
    after_state: dict = Column(JSON, nullable=True)
    result: str = Column(String, nullable=False)  # "success", "failed", "rolled_back"
    latency_ms: int = Column(Integer, nullable=True)
    metadata: dict = Column(JSON, nullable=True)
    timestamp: datetime = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

### 3.2 Audit Middleware

```python
class AuditMiddleware:
    """Intercepts all MCP tool calls for logging"""

    async def log_operation(
        tool_name: str,
        agent_id: str,
        session_id: str,
        operation: str,
        before_state: dict,
        after_state: dict,
        result: str,
        latency_ms: int
    ):
        log = AgentOperationLog(
            agent_id=agent_id,
            session_id=session_id,
            operation=operation,
            tool_name=tool_name,
            before_state=before_state,
            after_state=after_state,
            result=result,
            latency_ms=latency_ms
        )
        db.add(log)
```

### 3.3 Audit Query API

```python
# GET /api/v1/audit/logs?agent_id=xxx&session_id=xxx&operation=kg_create_entity
class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    page: int
    page_size: int
```

---

## 4. Multi-Step Undo System

### 4.1 UndoOperation Model

```python
class UndoOperation(Base):
    __tablename__ = "undo_operations"

    id: int = Column(Integer, primary_key=True)
    session_id: str = Column(String, nullable=False, index=True)
    operation_id: str = Column(String, nullable=False, unique=True)
    tool_name: str = Column(String, nullable=False)
    operation_type: str = Column(String, nullable=False)
    entity_type: str = Column(String, nullable=True)
    entity_id: str = Column(String, nullable=True)
    rollback_data: dict = Column(JSON, nullable=False)  # Data needed to undo
    status: str = Column(String, nullable=False)  # "pending", "completed", "failed"
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)
    completed_at: datetime = Column(DateTime(timezone=True), nullable=True)
```

### 4.2 UndoManager Service

```python
class UndoManager:
    """Manages multi-step undo operations"""

    def record(self, session_id: str, operation: UndoOperation):
        """Record operation to undo stack"""
        self.undo_stack[session_id].append(operation)

    def undo(self, session_id: str, steps: int = 1) -> UndoResult:
        """
        Undo N steps. Returns result for each step.
        """
        results = []
        for _ in range(steps):
            if not self.undo_stack.get(session_id):
                break
            op = self.undo_stack[session_id].pop()
            result = self._execute_rollback(op)
            results.append(result)
            self._log_undo(op, result)
        return results

    def _execute_rollback(self, op: UndoOperation) -> bool:
        """Execute rollback based on operation type"""
        if op.tool_name == "kg_create_entity":
            return self._rollback_create_entity(op)
        elif op.tool_name == "kg_update_entity":
            return self._rollback_update_entity(op)
        # ... other operation types
```

### 4.3 MCP Undo Tool

```python
@mcp.tool()
async def undo(
    session_id: str,
    agent_id: str,
    steps: int = 1
) -> UndoResponse:
    """Undo last N operations"""
    manager = UndoManager()
    results = manager.undo(session_id, steps)
    return UndoResponse(
        undone=len(results),
        results=results
    )
```

---

## 5. KG Write Operations with Conflict Detection

### 5.1 Write Flow

```
Agent calls kg_create_entity/kg_update_entity/kg_delete_relation
    ↓
AuditMiddleware records before_state
    ↓
KG write operation executes
    ↓
ConflictDetector checks for conflicts
    ↓
if severity >= 0.5:
    operation blocked → conflict created → pending review
    agent receives warning but operation logged
else:
    operation completes → auto-resolve if possible
    ↓
AuditMiddleware records after_state
    ↓
UndoManager records rollback data
```

### 5.2 Conflict Integration

```python
class KGWriteWithConflictDetection:
    """Wrapper for KG write operations with conflict detection"""

    async def execute(self, tool_name: str, entity_data: dict, agent_id: str, session_id: str):
        # Check for conflicts before write
        conflicts = self.conflict_detector.detect(entity_data)

        for conflict in conflicts:
            if conflict.severity >= 0.5:
                # Block operation, create pending conflict
                self.conflict_service.create_pending_conflict(conflict, agent_id)
                raise ConflictDetectedError(conflict)

        # Execute write if no high-severity conflicts
        result = await self.execute_write(tool_name, entity_data)

        # Record for undo
        self.undo_manager.record(session_id, result.operation_id, tool_name, entity_data)

        return result
```

---

## 6. File Structure

```
backend/app/
├── mcp/
│   ├── __init__.py
│   ├── tool_adapters.py       # MCP tool definitions
│   ├── kg_tools.py            # KG operation tools
│   ├── mastery_tools.py       # Mastery/BKT tools
│   ├── tutor_tools.py         # Tutor session tools
│   ├── irt_tools.py           # IRT calibration tools
│   ├── fsrs_tools.py          # FSRS scheduling tools
│   └── expert_tools.py        # Expert reviewer tools
├── services/
│   ├── audit_service.py       # Audit logging service
│   └── undo_manager.py        # Multi-step undo manager
├── models/
│   ├── audit.py               # AgentOperationLog model
│   └── undo.py                # UndoOperation model
├── middleware/
│   └── audit_middleware.py     # Audit logging middleware
└── api/v1/routes/
    └── audit.py               # Audit log API routes
```

---

## 7. MCP Server Configuration

The FastApiMCP server is already mounted at `/mcp`. We need to:

1. Define MCP tools for each API endpoint
2. Register tools with FastApiMCP
3. Add audit middleware to all tools

```python
# In main.py, replace simple mount with full tool registration
mcp_server = FastApiMCP(application)

# Register all tools
mcp_server.register(kg_query)
mcp_server.register(kg_create_entity)
# ... all other tools
```

---

## 8. API Endpoints for Audit & Undo

### GET /api/v1/audit/logs
Query audit logs with filters

### GET /api/v1/audit/logs/{operation_id}
Get single operation details

### POST /api/v1/undo
Execute undo operation

### GET /api/v1/undo/stack/{session_id}
Get current undo stack for session

---

## 9. Acceptance Criteria

1. **MCP Tools**: All REST API endpoints exposed as MCP tools
2. **Audit Logging**: Every tool call logged with before/after state
3. **Multi-step Undo**: Can undo up to 10 operations in a session
4. **Conflict Detection**: KG writes check conflicts before execution
5. **Agent Isolation**: Each agent has isolated session and undo stack
6. **Performance**: Tool invocation latency < 200ms (excluding LLM calls)