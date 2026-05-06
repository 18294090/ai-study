# Hermes Agent 集成设计 (Phase 1: ExamAgent)

## 概述

将 Hermes Agent 集成到现有 FastAPI 系统，作为 AI agent 层的主力框架。Phase 1 聚焦于 ExamAgent 迁移，验证架构可行性。

## 架构决策

### 集成方式

**选项 A: Hermes 作为 FastAPI 的一部分**

```
FastAPI (uvicorn)
├── /api/v1/... (现有 12 routes)
└── /hermes/* (Hermes HTTP gateway)
```

Hermes 作为 FastAPI 内部服务运行，通过内部调用或 HTTP gateway 暴露 skills。

**选择理由**:
- 保留现有的 BKT/IRT/FSRS 算法层
- 渐进式迁移，风险可控
- 统一部署和运维

### Skill 职责边界

**选项 B: orchestrator 模式**

exam_skill 作为流程编排器，调用独立 tools：

```
exam_skill
├── parse_pdf_tool (MinerU PDF 解析)
├── extract_questions_tool (LLM 提取)
├── validate_question_tool (规则验证)
└── refine_question_tool (LLM 精炼)
```

**选择理由**:
- 更符合 Hermes 架构风格
- PDF 解析作为独立 tool 可复用
- 解耦后易于测试

### 数据处理

**选项 B: FastAPI route 负责存储**

```
Hermes skill → 返回 {questions, metadata} → FastAPI route → 写入 DB + 更新 KG
```

**选择理由**:
- 保持 FastAPI 作为数据入口点
- 与现有 `/knowledge_extraction` route 解耦
- 便于事务控制

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI (uvicorn)                      │
├─────────────────────────────────────────────────────────────┤
│  核心算法层 (保留不动)                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │
│  │   BKT   │  │ IRT-2PL │  │  FSRS   │  │ MasteryTrack│   │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Hermes Runtime (新增)                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Hermes HTTP Gateway (/hermes/*)                     │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │  exam_skill                                         │  │
│  │  ├── parse_pdf_tool (MinerU)                        │  │
│  │  ├── extract_questions_tool (LLM)                   │  │
│  │  ├── validate_question_tool                         │  │
│  │  └── refine_question_tool (LLM)                     │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  现有 AI Agent (待迁移)                                    │
│  ├── Socratic Tutor (6-state machine)                     │
│  ├── Expert Reviewer (conflict detection)                  │
│  ├── Subject Detector (LLM 调用)                          │
│  ├── Learning Advisor (LLM 调用)                           │
│  └── Group Advisor (LLM 调用)                             │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

```
1. POST /api/v1/knowledge_extraction/exam
   │
2. FastAPI route 调用 Hermes skill
   │
3. Hermes runtime 执行 exam_skill
   │   ├── parse_pdf_tool (MinerU) → markdown
   │   ├── extract_questions_tool (LLM) → questions[]
   │   ├── validate_question_tool → validation[]
   │   └── refine_question_tool (if needed) → refined[]
   │
4. exam_skill 返回 {questions, metadata, confidence}
   │
5. FastAPI route 处理结果
   │   ├── 写入 questions 表
   │   ├── 更新 knowledge graph (knowledge_extraction.py)
   │   └── 返回 ExtractionResult 给 client
```

## 文件结构

```
backend/app/
├── hermes/                          # 新增: Hermes 集成
│   ├── __init__.py
│   ├── runtime.py                   # Hermes runtime 封装
│   ├── gateway.py                   # HTTP gateway 路由
│   ├── skills/
│   │   ├── __init__.py
│   │   └── exam_skill.py           # 试题提取 skill
│   └── tools/
│       ├── __init__.py
│       ├── parse_pdf_tool.py       # MinerU 封装
│       ├── extract_questions_tool.py
│       └── validate_question_tool.py
│
├── services/exam_parser/            # 保留: LangGraph 实现 (Phase 2 清理)
│   ├── agent/
│   │   ├── exam_agent.py
│   │   ├── state.py
│   │   └── tools.py
│   └── ...
│
└── api/v1/
    └── knowledge_extraction.py      # 修改: 调用 Hermes 替代 LangGraph

hermes/                              # 新增: Hermes 配置
├── config.yaml
├── skills/
│   └── exam_skill.md
└── memory/                          # Hermes memory 存储
```

## Skill 实现

### exam_skill.md

```markdown
# Exam Extraction Skill

## Purpose
Extract questions from exam PDFs using LLM with MinerU parsing.

## Tools
- parse_pdf: Parse PDF using MinerU
- extract_questions: Extract questions using LLM
- validate_question: Validate extracted question
- refine_question: Refine low-confidence questions

## Flow
1. Parse PDF → markdown
2. For each page:
   a. Extract questions using LLM
   b. Validate each question
   c. If low confidence, refine
3. Return extracted questions with metadata

## Output
{
  "questions": [...],
  "metadata": {
    "total_pages": int,
    "questions_extracted": int,
    "low_confidence_count": int
  },
  "confidence": float
}
```

### parse_pdf_tool

```python
@hermes.tool()
def parse_pdf(file_path: str) -> dict:
    """Parse PDF using MinerU and return markdown."""
    from app.services.exam_parser.parsers.mineru_parser import MinerUAdapter
    adapter = MinerUAdapter()
    result = adapter.parse(file_path)
    return {"markdown": result.markdown, "images": result.images}
```

## API 修改

### 新增端点 (可选)

```python
# /hermes/* - Hermes gateway
@router.post("/hermes/exam/extract")
async def hermes_exam_extract(file_path: str, ...):
    result = await hermes_runtime.run("exam_skill", {"file_path": file_path})
    # 处理结果，写入 DB
    return result
```

### 修改现有端点

```python
# /api/v1/knowledge_extraction/exam
@router.post("/exam")
async def extract_exam(
    file_path: str,
    subject_id: Optional[int] = None,
    use_hermes: bool = True  # 开关：Hermes vs 现有 LangGraph
):
    if use_hermes:
        result = await hermes_runtime.run("exam_skill", {"file_path": file_path})
    else:
        result = await legacy_exam_agent.run(file_path)  # 保留旧实现

    # 统一处理
    await save_questions(result["questions"])
    await update_knowledge_graph(result["questions"])

    return result
```

## 配置

### hermes/config.yaml

```yaml
hermes:
  runtime:
    host: "127.0.0.1"
    port: 8080
    max_iterations: 90
    timeout: 300

  memory:
    type: "sqlite"  # 或 "postgres"
    path: "~/.hermes/memory.db"

  skills:
    exam_skill:
      enabled: true
      confidence_threshold: 0.6
      tools:
        - parse_pdf
        - extract_questions
        - validate_question
        - refine_question

  providers:
    default: "openrouter"
    openrouter:
      api_key: "${OPENROUTER_API_KEY}"
      model: "deepseek/deepseek-chat-v3"

  sandbox:
    enabled: true
    backend: "docker"
    isolation: true
```

## 迁移计划

### Phase 1 (1-2 周): ExamAgent 迁移

1. 安装 Hermes Agent
2. 配置 Hermes runtime 和 HTTP gateway
3. 创建 exam_skill 和 tools
4. 修改 FastAPI route 支持 Hermes 调用
5. 对比评估新旧实现效果
6. 如满意，删除 LangGraph 实现

### Phase 2 (待定): Socratic Tutor

- 创建 tutor_skill
- 保留 6-state machine 核心逻辑
- Hermes 负责对话管理和 memory

### Phase 3 (待定): Advisor 整合

- 合并 Subject Detector + Learning Advisor + Group Advisor → advisor_skill

### Phase 4 (待定): GraphRAG

- 集成 LightRAG
- 创建 graph_rag_skill

## 保留模块 (不迁移)

以下模块是核心算法，必须保留：

- `backend/app/kg/learner/bkt.py` - Bayesian Knowledge Tracing
- `backend/app/kg/learner/irt.py` - Item Response Theory (2PL)
- `backend/app/kg/learner/fsrs.py` - Free Spaced Repetition Scheduler
- `backend/app/mastery/` - Mastery tracking

这些通过 FastAPI route 调用，不受 Hermes 迁移影响。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Hermes 资源占用高 | 配置合理的 memory limit 和 timeout |
| 数据安全 (ByteDance 无此问题 - Hermes 是 MIT) | Hermes 来自 Nous Research，无此顾虑 |
| 迁移期间系统不稳定 | 保留旧实现，通过 `use_hermes` 开关切换 |
| skill 学习曲线 | 先从 exam_skill 开始，积累经验后再扩展 |

## 成功标准

1. Hermes exam_skill 提取质量 >= 现有 LangGraph 实现
2. 平均提取时间 <= 现有实现
3. 错误率 <= 5%
4. skill 可通过配置开关启用/禁用
5. 现有 API 兼容，不破坏现有调用方