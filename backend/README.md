# LearnHub — AI-Native 教育平台

> 面向 K12 / 高校的智能学习系统：知识图谱 + 间隔复习 + 能力评估 + AI 辅导一体化

---

## 技术栈

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.116 + Uvicorn（asyncio） |
| 数据库 | PostgreSQL 16 + asyncpg + Alembic |
| 知识图谱 | Neo4j 5.x + GDS（Leiden 社区检测）|
| 向量存储 | Qdrant 1.x |
| 缓存 | Redis 5+ |
| AI / LLM | LangChain + LangGraph Agent 编排 |
| 嵌入模型 | BGE-M3（FlagEmbedding）+ Cohere Rerank |
| PDF 解析 | PyMuPDF + PyPDF + MinerU / Docling（可选）|
| 合规 | RDFLib + PySHACL（JYT-0644 国标本体）|
| 评估 | RAGAS + 自研 triple-PRF 指标 |
| 依赖管理 | Poetry（package-mode = false）|

---

## 快速启动

### 前置依赖

- Python 3.12+
- PostgreSQL 16
- Neo4j 5.x（+ GDS 插件）
- Qdrant
- Redis

### 安装

```bash
# 克隆仓库后在项目根目录执行
make install          # 安装 Python 依赖（自动 bootstrap Poetry）
make install-torch    # 安装 PyTorch CUDA（可选，GPU 推理用）
```

### 配置环境变量

```bash
# backend/.env（可从 backend/.env.example 复制）
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/learnhub
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your_neo4j_password
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
SECRET_KEY=your_jwt_secret_key
```

### 启动开发服务器

```bash
make dev              # uvicorn --reload，监听 :8000
```

### 数据库迁移

```bash
make migration MSG="add_xxx_table"   # 生成迁移文件
make migrate                          # 应用迁移
```

### 其他常用命令

```bash
make test    # 运行测试（pytest）
make lint    # ruff + mypy
make format  # ruff format
make shell   # 进入 Poetry 虚拟环境 shell
make status  # 服务健康检查
```

---

## 项目结构

```
backend/
├── pyproject.toml          # Poetry 配置（package-mode = false）
├── alembic.ini
├── app/
│   ├── main.py             # FastAPI 应用入口，lifespan 管理
│   ├── api/v1/             # REST API 路由（versioned）
│   │   └── routes/
│   │       ├── questions.py
│   │       ├── subjects.py
│   │       ├── knowledge_points.py
│   │       └── knowledge_extraction.py
│   ├── core/               # 横切关注点
│   │   ├── config.py       # pydantic-settings 配置
│   │   ├── auth.py         # JWT 认证
│   │   ├── permissions.py  # RBAC 权限帮助函数
│   │   ├── security.py     # 安全中间件
│   │   └── logging.py      # 结构化日志
│   ├── models/             # SQLAlchemy ORM 模型
│   ├── schemas/            # Pydantic 请求/响应模型
│   ├── crud/               # 基础 CRUD 操作
│   ├── services/           # 业务逻辑
│   │   ├── fsrs_scheduler.py        # 间隔复习（FSRS 算法）
│   │   ├── irt_ability.py           # 能力估计（IRT EAP）
│   │   ├── irt_calibration.py       # 题目标定（IRT 3PL）
│   │   ├── bkt_service.py           # 知识追踪（BKT）
│   │   ├── tutor_state_machine.py   # AI 辅导状态机
│   │   ├── knowledge_extraction.py  # KG 提取服务
│   │   ├── question_vectorization.py
│   │   └── exam_parser/             # 试卷解析（PDF/DOCX/Image）
│   ├── kg/                 # 知识图谱流水线（详见 kg/README.md）
│   ├── mcp/                # MCP 工具服务器（可选）
│   ├── db/                 # 数据库会话 / Neo4j 工具
│   └── tasks/              # Celery 后台任务
└── migrations/             # Alembic 迁移脚本
```

---

## 核心算法模块

### 间隔复习 — FSRS

`app/services/fsrs_scheduler.py` 实现 Free Spaced Repetition Scheduler v4，包含参数优化器。支持 1-4 评分，自动计算下次复习间隔。

### 能力评估 — IRT

`app/services/irt_ability.py` 使用三参数 IRT 模型（3PL）和 EAP 贝叶斯能力估计（网格点 -3 ~ +3），要求至少 5 条答题记录。`irt_calibration.py` 负责题目参数标定。

### 知识追踪 — BKT

`app/services/bkt_service.py` 实现贝叶斯知识追踪，按知识点维度跟踪掌握概率。

### AI 辅导状态机

`app/services/tutor_state_machine.py` 实现 6 状态辅导流程：
`DIAGNOSE → HINT_LADDER → GUIDE → COUNTER_EXAMPLE → CONSOLIDATE → ESCALATE`

三级渐进提示（L1-L3），引导式而非直接给答案，支持知识图谱引用。

---

## 安全说明

- 数据库密码、JWT 密钥等**必须**通过 `.env` 文件或环境变量注入，禁止硬编码
- 生产环境请将 `CREATE_DB_TABLES` 设为 `false`，使用 Alembic 迁移
- CORS `allow_origins` 生产环境应替换为实际前端域名
