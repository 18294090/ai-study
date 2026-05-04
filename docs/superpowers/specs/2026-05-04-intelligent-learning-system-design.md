# LearnHub - 智慧学习系统设计文档

> **Date:** 2026-05-04
> **Status:** Approved
> **Version:** 2.0（融入 GraphRAG / IRT-BKT / 推理模型 / 程序化内容生成 / 评测体系）

## 0. 版本变更摘要 (v1.2 → v2.0)

| 类别 | v1.2 | v2.0 |
|---|---|---|
| 教学法引擎 | 仅布鲁姆 + 艾宾浩斯 | 引入 **BKT/DKT + IRT 2PL** 双模型，mastery state 一等数据 |
| 知识图谱 | 单层 schema (7 实体 + 10 关系) | **三层 KG**：学科图谱 / 教学图谱 / 认知诊断图谱 |
| 检索范式 | KG 与 RAG 解耦 | **GraphRAG**：社区摘要 + 实体扩展 + 三元组锚定 |
| LLM 调用 | GPT-4o / Claude-3.5 一刀切 | **分级路由**：推理模型 (o3/R1) 处理难任务，小模型处理高频任务，结构化输出 + prompt caching |
| 实体消歧 | Levenshtein 编辑距离 | **BGE-M3 embedding + 类型约束 + LLM verifier** 三阶段 |
| AIGC 内容 | Sora 直接生成视频 | **程序化动画 (Manim/Remotion) + LLM 旁白 + 互动 widget** 为主，端到端视频为辅 |
| 出题质量 | 静态难度 1-5 | **IRT 难度反求 + misconception 干扰项库 + 双 LLM 交叉校验 + 求解器 ground-truth** |
| 内容治理 | 完全去中心化 | **专家审核池 + 社区贡献池** 双层；用户分级 (learner / contributor / verified organizer) |
| 评测体系 | 无 | **CI 评测集**：500 三元组 / 200 题 / 100 tutoring dialog |
| 安全 | 未提 | Prompt injection 防御、内容投毒检测、AIGC 显著标识、机器遗忘 |
| Agent 定位 | 含糊（DeerFlow 一刀切） | **不以 Agent 为架构中心**：核心是 GraphRAG + 教学法引擎；Agent 仅在受约束的执行层（Tutor、研究型任务） |

---

## 1. 核心理念

**双层去中心化学习社区** —— 严肃知识由专家与算法共同把关，长尾知识由社区共建。AI 不是答案分发器，而是**苏格拉底式 1:1 导师**。每位用户拥有完整数据主权与可解释的学习画像。

## 2. 核心设计原则

| 原则 | 描述 |
|------|------|
| **教学优先** | 所有功能服从学习科学（Mastery Learning、ZPD、检索练习、间隔重复） |
| **可解释 AI** | 推荐/诊断/打分必须给出 KG 路径与置信度 |
| **用户中心** | 完整数据主权，可导出、删除、撤回授权、机器遗忘 |
| **角色分级** | learner → contributor → verified organizer，权限随声誉解锁 |
| **质量双轨** | 专家审核内容池 + 社区贡献内容池，分别加权推荐 |
| **成本可控** | 模型分级路由，长上下文 + prompt caching，冷热分层缓存 |
| **合规优先** | GDPR、网安法、未成年人保护、教培双减、AIGC 显著标识 |

## 3. 系统架构

### 3.0 架构原则：**Agent 不是中心**

架构以 **教学法 (L0) → 知识表示 GraphRAG (L1) → 评测 (L2) → 执行形态 (L3)** 自顶向下分层。Agent 仅是 L3 的一种执行形态，受 L0/L1/L2 严格约束：

- **能写成确定性 DAG 的，不做成 Agent**：KG 抽取/融合/社区检测、IRT/BKT 推断、FSRS 调度、路径规划、内容校验流水线全部走 LangGraph DAG + structured outputs。
- **必须多轮交互的才 Agent 化**，且必须叠加状态机与教学法约束：Tutor 对话、Expert Reviewer 协助、跨教材研究。
- **所有 Agent 输出必须可锚定到 KG**（citations 指向 KG 节点 / 章节），且经过 evaluator/verifier。
- **Agent 不直接持久化**：写入 KG、Mastery、内容池等关键状态由确定性服务执行，Agent 通过受控 API 触发。

> 反例：把 Tutor 做成自由 ReAct Agent → 教学质量不稳、不可评测、幻觉、成本失控（Khanmigo 早期教训）。

### 3.1 分层视图

```
┌────────────────────────────────────────────────────────────────────────┐
│                         应用层 (Web / Mobile / API)                     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│                  教学法引擎 Pedagogical Engine                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐      │
│  │ Mastery Model│  │  IRT 难度估计 │  │ Socratic Tutor (Dialog)  │      │
│  │ (BKT / DKT)  │  │  (2PL/3PL)   │  │ State Machine + Verifier │      │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│              统一 GraphRAG 检索层 (所有下游任务的入口)                   │
│   query → community summary → entity expansion → triple-grounded         │
│   ┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│   │ Vector DB  │  │ KG (Neo4j)   │  │ Community    │  │ Reranker   │  │
│   │ (BGE-M3)   │  │ 三层 schema  │  │ Summaries    │  │ (Cohere)   │  │
│   └────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│                       LLM 路由 (Model Router)                          │
│   推理模型 (o3 / DeepSeek-R1)  │  通用 (GPT-4o / Claude 3.7)            │
│   蒸馏小模型 (Qwen-7B / R1-D)  │  Embedding (BGE-M3 multimodal)         │
│   ★ 强制 structured outputs / prompt caching / DSPy 编译式优化          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│                          领域服务                                      │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│ │ 知识图谱  │ │  题库     │ │ 学习路径 │ │  导师    │ │ 内容生成     │  │
│ │ KG 服务   │ │ + IRT    │ │ + 推荐   │ │ Tutor    │ │ AIGC 程序化  │  │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│ ┌──────────┐ ┌──────────────────┐ ┌──────────┐ ┌──────────────────┐    │
│ │ 群组/社交│ │ 游戏化 / 成就     │ │ 内容审核 │ │ 合规 / 机器遗忘   │    │
│ └──────────┘ └──────────────────┘ └──────────┘ └──────────────────┘    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴─────────────────────────────────────┐
│                          数据层                                        │
│  PostgreSQL (核心) │ Neo4j (KG) │ Qdrant/Milvus (向量) │ Redis (缓存)   │
│  ClickHouse (学习行为流) │ S3 (静态资源) │ DVC (评测集版本)              │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 多智能体架构理念引入（2026年升级）

为顺应AI原生教育系统的发展趋势，LearnHub将引入多智能体（Multi-Agent）架构，提升系统智能化、灵活性与可扩展性。

#### 多智能体架构核心要点

- **智能体分工协作**：将复杂教育任务拆分为教学、评测、组卷、学情分析、教研等专属智能体（Agent），各司其职，协同完成全链路任务。
- **元智能体编排**：引入MetaAgent（元智能体）负责全局任务调度、智能体协作与冲突解决，支持任务分解、角色分配、结果整合、记忆管理等能力。
- **动态扩展与模块化**：新功能可通过增加智能体灵活扩展，无需重构主流程。各Agent可独立开发、测试、部署，提升系统可维护性。
- **个性化与自适应**：多智能体可根据学生实时状态动态分配任务，实现更细粒度的个性化学习、诊断和推荐。
- **系统鲁棒性与可解释性**：智能体间可互为校验、补充，降低单点失效风险。每个Agent的决策过程可独立追踪，提升系统整体可解释性。

#### 典型智能体角色

- 教学智能体（Teaching Agent）：负责课程内容讲解、教案生成、课堂互动
- 学习智能体（Learning Agent）：陪伴学生学习，提供个性化辅导和答疑
- 评测智能体（Assessment Agent）：试题生成、组卷、批改、学情分析
- 管理智能体（Management Agent）：班级管理、排课、考勤、成绩管理
- 教研智能体（Research Agent）：分析教学数据，发现问题，提供教研建议
- 苏格拉底助教（Socratic Tutor Agent）：通过提问引导学生思考，培养批判性思维

#### 架构集成方式

- 主流程仍以LangGraph DAG为骨干，确定性任务优先DAG化，需多轮交互/复杂决策的场景采用多智能体协作。
- 智能体间通过标准化消息协议通信，支持动态加载与卸载。
- 可逐步在评测、组卷、学情分析、个性化推荐等模块试点Agent化，逐步推广至全系统。

#### 未来演进

- 便于后续引入端云混合、联邦学习、数字孪生等更高级特性。
- 对标国际领先案例（如Fermi.ai、OpenAI Study and Learn），实现AI原生、可持续演进的智慧学习平台。

## 4. 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|---|
| **文档解析** | MinerU + Marker + Nougat (公式) | 多解析器投票，公式专用 |
| **KG 存储** | Neo4j (主) + Memgraph (热查询副本) | 支持 GDS Leiden 社区检测 |
| **向量库** | Qdrant | 多模态统一空间 (BGE-M3) |
| **核心 DB** | PostgreSQL 16 | row-level security |
| **行为流** | ClickHouse | 学习事件秒级分析 |
| **缓存** | Redis + DragonflyDB | prompt cache + session |
| **对象存储** | S3 兼容 (MinIO) | 内容池、视频缓存 |
| **推理 LLM** | OpenAI o3 / DeepSeek-R1 / Claude 3.7 thinking | 出题、解题、KG 抽取 verifier |
| **通用 LLM** | GPT-4o / Claude 3.7 / Gemini 2.5 (1M ctx) | 长上下文章节抽取 |
| **小模型** | Qwen2.5-7B / R1-Distill-14B (vLLM 自托管) | 高频低难任务 |
| **Embedding** | BGE-M3 (文本+多模态)、Cohere Rerank v3 | 统一向量空间 |
| **结构化输出** | OpenAI structured outputs / Outlines / xgrammar | 零解析失败 |
| **生产管线编排** | LangGraph DAG + Temporal + DSPy MIPROv2 | 高 SLA、批处理、CI 评测准入；KG 抽取/Tutor/IRT 等核心路径 |
| **研究型 Agent（可选）** | DeerFlow 2.0 + MCP | 跨教材调研、Expert Reviewer 协助；不进入高频生产路径 |
| **后端** | FastAPI + Temporal (workflow) | 长流程编排 |
| **前端** | Next.js 15 + React + Tailwind + Manim/Remotion | 程序化动画 |
| **互动 widget** | MDX + 自研 React 组件库 (对标 Brilliant.org) | 可嵌入式微交互 |
| **可计算公式** | LaTeX + SymPy AST | 步骤级解题校验 |
| **评测** | Ragas + Promptfoo + 自建 harness | CI 评测准入 |
| **观测** | OpenTelemetry + Langfuse | LLM trace + 成本归因 |
| **部署** | Docker + Kubernetes + Istio | 多租户、多区域 |

## 5. 用户角色与权限分级

| 角色 | 获取方式 | 权限 |
|------|---|------|
| **Learner（默认）** | 注册即得 | 学习、刷题、加入群组、提问、查看公开 KG |
| **Contributor** | 累计贡献分 ≥ 阈值 | 上传资料、提交 KG 修订、创建普通群组（内容仅入社区池） |
| **Verified Organizer** | 实名 + 资质审核 | 发布到专家池、组织有学分价值的活动、查看群组分析 |
| **Expert Reviewer** | 邀请制 | 审核 AIGC 内容、仲裁 KG 冲突、设定学科基准 |

> **关键差异**：v1 "无权威教师" 改为 **"分级权威 + 社区共建"**，避免内容投毒与知识失真。

## 6. 核心功能模块

### 6.1 教学法引擎 (Pedagogical Engine) ★ v2.0 新增核心

| 子模块 | 描述 |
|---|---|
| **Mastery Model** | 每个用户对每个 KG 概念维护掌握概率 `p ∈ [0,1]`，使用 BKT (Bayesian Knowledge Tracing) 在线更新；高级版本切换 DKT (LSTM/Transformer) |
| **IRT 难度估计** | 题目参数 `(a, b, c)` 由作答数据通过 EM 算法持续反求；新题冷启动用 LLM 估计 + 主动学习 |
| **ZPD 选题** | 选择 `P(correct \| θ_user, item) ∈ [0.6, 0.8]` 的题目，最大化学习增益 |
| **Spaced Repetition** | FSRS-5 算法（优于 SM-2/Anki 默认）+ 概念依赖加权 |
| **Socratic Tutor** | 对话状态机：`诊断 misconception → 给提示 (hint ladder) → 引导推理 → 反例检验 → 巩固`；禁止直接给答案 |
| **可解释诊断** | 每次诊断输出 KG 路径 + 概率：「在 X 上掌握度 0.4，因前置 Y 仅 0.5」 |

### 6.2 知识图谱 (三层 Schema)

```
Layer 1 — 学科知识图谱 (Domain KG)
   实体：concept / formula / theorem / person / event / location / work / time / dataset
   关系：is_a / part_of / causes / equivalent_to / generalizes / contradicts /
         applies_to / requires / before / after / similar_to / defined_by / example_of
   属性：name, description, latex (公式), sympy_ast (可计算), source_doc, confidence

Layer 2 — 教学知识图谱 (Pedagogical KG)
   实体：learning_objective / lesson / activity / assessment / misconception
   关系：teaches (lesson → concept) / prerequisite_of / assesses / addresses_misconception /
         estimated_minutes / bloom_level (remember…create) / dok_level (1-4)

Layer 3 — 认知诊断图谱 (Cognitive Diagnostic KG)
   实体：skill / sub_skill / Q-matrix entry
   关系：requires_skill (item → skill) / composed_of / mastery_threshold
   ★ 用于 BKT/DKT 训练与诊断
```

**关键能力**：
- **GraphRAG 社区检测**：Leiden 算法 → 层次化社区摘要 → 全局问答能力
- **可计算公式**：LaTeX + SymPy AST，支持「步骤级解题校验」（对标 Wolfram）
- **跨教材融合**：embedding + LLM verifier 对齐同义概念，矛盾时进入 Expert Reviewer 仲裁队列
- **增量更新与版本化**：每次教材改版生成 diff，影响传播至教学层与诊断层
- **章节锚定**：每条三元组保留 `(textbook_id, chapter_id, paragraph_offset)`，可一键回引原文

### 6.3 GraphRAG 统一检索层

```
用户 query
   ↓
意图分类 (factual / procedural / explanatory / meta)
   ↓
混合检索：
   ├─ 向量召回 (BGE-M3 multimodal, top-50)
   ├─ KG 实体匹配 + 1-hop 邻居扩展
   └─ 社区摘要召回 (全局型问题)
   ↓
Cohere Rerank v3 → top-10
   ↓
推理模型生成 + 强制三元组锚定 (citations 必须指向 KG 节点 / 章节)
   ↓
Self-RAG verifier (检索是否充分 / 是否有幻觉)
   ↓
输出 + KG 路径解释
```

> 所有下游任务（出题、辅导、推荐、内容生成）共用此检索层。

### 6.4 题库系统 (含 AIGC 出题)

| 功能 | v2.0 改进 |
|---|---|
| **试卷导入** | MinerU + Nougat 公式专用解析，OCR 投票 |
| **自动标注** | 推理模型抽取 → KG 锚定 → IRT 冷启动估计 |
| **IRT 标定** | 持续作答数据反求 `(a, b, c)`；定期 EM 重估 |
| **智能组卷** | 给定目标 mastery 增益 → 解优化（线性规划/贪心） |
| **AIGC 出题** | 模板化 + 参数化生成（防记忆）；推理模型生成 → 求解器/SymPy ground-truth → 第二 LLM 反向解题校验 |
| **干扰项生成** | 基于 misconception 库（"常见错误的精炼表征"）生成有教学价值的错误选项 |
| **质量准入** | 必过：求解器一致性 + 双 LLM 一致性 + 难度落入目标区间；否则进入人工队列 |
| **题目改编** | 同 KG 节点 + 不同认知层级 (DOK 1→4) + 不同情境化包装 |

### 6.5 学习路径服务

- **诊断**：BKT 后验 + 自适应预测 (CAT, Computerized Adaptive Testing)，5-10 题完成定标
- **路径规划**：在教学 KG 上做最短"前置依赖"DAG 拓扑序，叠加 mastery gap → 最大增益贪心
- **遗忘管理**：FSRS-5 + 知识依赖衰减传播
- **可解释推荐**：每条推荐附 KG 路径 + 预期 mastery 增益 + 预计耗时

### 6.6 苏格拉底式 AI 导师 (Tutor)

> **架构定位**：Tutor 是**受约束 Agent**，不是自由 ReAct。其行为由下方状态机驱动，每一轮输出强制经过 (a) 教学法策略校验 (b) GraphRAG 三元组锚定 (c) prompt injection 检测 (d) 不直接给答案规则。状态机由 LangGraph 实现；LLM 仅负责单轮自然语言生成。

| 状态 | 行为 |
|---|---|
| `diagnose` | 通过追问识别 misconception 节点 |
| `hint_ladder` | 给提示 L1（方向）→ L2（关键概念）→ L3（半步推导），逐级展开 |
| `guide` | 引导学生自己产出推理；禁止给最终答案 |
| `counter_example` | 用反例检验是否真理解 |
| `consolidate` | 总结 KG 路径 + 推荐巩固题 |
| `escalate` | 三轮无进展 → 切换为讲解模式或推 expert reviewer |

★ 所有 Tutor 输出经过 **prompt injection 检测**（学生题目可能注入"忽略前文"等指令）。

### 6.7 群组与社交（双轨内容池）

- **专家审核池**：Verified Organizer / Expert 发布，进入主推荐流，权重高
- **社区贡献池**：Contributor 发布，进入"探索"流，需达到投票阈值才进入主推荐
- **群组分级**：公开群 / 私有群 / 学分群（需机构认证）
- **学习搭档**：基于 mastery 向量相似度 + 互补度匹配（不只兴趣）

### 6.8 内容生成服务 (AIGC) — 程序化优先

| 类型 | 主路线 | 备选 |
|---|---|---|
| **教学动画** | KG 节点 → LLM 生成 Manim/Remotion 脚本 → 渲染 → TTS 旁白 | Sora/Pika 端到端（仅作为风格化片头） |
| **图解/流程图** | LLM → Mermaid / D2 / Graphviz → SVG | DALL-E（装饰性插图） |
| **互动 widget** | MDX + 自研 React 微件（拖拽、可视化、模拟器） | — |
| **学习指南** | GraphRAG + 推理模型生成 → 强制三元组引用 | — |
| **互动测验** | 6.4 出题流水线复用 | — |

**质量控制流水线**：

```
KG 节点 + 学情画像
   ↓
内容规划（选择媒介、教学法策略）
   ↓
程序化生成（Manim/Mermaid/MDX 代码）
   ↓
自动校验：编译通过 + 静态规则 + LLM 事实性检查 + 求解器一致性（如含公式）
   ↓
小流量灰度 (A/B) → 用户互动指标（完成率/再访率）→ 自动晋级或淘汰
   ↓
重要知识点：Expert Reviewer 人工抽检 + AIGC 显著标识水印
```

### 6.9 何时用 Agent / 何时不用（决策矩阵）

| 场景 | 形态 | 理由 |
|---|---|---|
| KG 抽取 / 融合 / 社区检测 | **DAG**（LangGraph + structured outputs） | 可批处理、可评测、需 CI 准入 |
| IRT 参数反求 / BKT 更新 / FSRS 调度 | **算法 + 批处理** | 数值方法，无需 LLM 决策 |
| 学习路径规划 | **图算法**（拓扑序 + 增益贪心） | 确定性 + 可解释 |
| 内容质量校验 | **规则 + 求解器 + 双 LLM 投票** | 需可重放 |
| GraphRAG 检索 | **DAG + Self-RAG mini-loop** | 主路径确定，仅反思环节有限 agent 化 |
| 苏格拉底 Tutor | **状态机驱动的受限 Agent** | 多轮交互不可预先 DAG 化，但必须教学法约束 |
| 题目反向求解校验 | **推理模型 + 工具调用 (SymPy/计算器)** | 多步推理 + 工具，但无对话 |
| 跨教材研究 / Expert Reviewer 协助 | **研究型 Agent (DeerFlow)** | 探索性、低频、人机协作 |
| 教师端创作辅助 | **Agent + tools** | 开放式任务 |

> 默认值：**先 DAG，后 Agent**。任何 Agent 化提案必须回答：(1) 为什么不能 DAG？ (2) 评测怎么做？ (3) 成本上限？ (4) 教学法约束如何强制？

### 6.10 监控、报告与隐私

- 学习报告：周报/月报 + 可解释性图谱
- 数据导出：JSON + 学习画像可移植格式
- **机器遗忘 (Machine Unlearning)**：用户撤回授权时执行 SISA / influence-based unlearning，并保存证明
- **AIGC 显著标识**：所有生成内容元数据带 `c2pa` 签名 + UI 标识

## 7. 数据模型（关键差异）


```python
User:
  ...
  consent_for_ai_training: ConsentRecord  # 含目的限定、撤回时间戳

MasteryState:
  user_id: str
  concept_id: str
  prob_known: float          # BKT 后验
  last_practice_at: datetime
  fsrs_state: dict           # 间隔重复状态
  evidence: List[ItemId]     # 支撑证据

Question:
  ...
  irt_params: {a: float, b: float, c: float, theta_uncertainty: float}
  knowledge_skills: List[skill_id]   # Q-matrix
  misconceptions_targeted: List[misconception_id]
  solver_verified: bool
  cross_llm_agreement: float

Misconception:
  id: str
  description: str
  related_concepts: List[concept_id]
  example_wrong_answers: List[str]

Content:
  ...
  generation_pipeline: str            # manim / remotion / mermaid / sora
  source_kg_nodes: List[concept_id]
  c2pa_signature: str
  pool: Literal["expert", "community"]
  quality_metrics: {factuality, engagement, completion_rate}

KGTriple:
  ...
  textbook_anchor: {textbook_id, chapter_id, paragraph_offset}
  layer: Literal["domain", "pedagogical", "diagnostic"]
  community_id: Optional[str]         # Leiden 社区
```

## 8. API 设计（v2.0 增量）

```
# 教学法引擎
GET  /api/v1/mastery/:user_id              # 当前 mastery 向量
POST /api/v1/mastery/update                # 提交作答事件，BKT 更新
GET  /api/v1/diagnose/cat                  # 自适应测试下一题

# GraphRAG 统一检索
POST /api/v1/rag/query                     # body: {q, mode: factual|global|tutor}
                                           # resp: {answer, citations[], kg_paths[]}

# Tutor
POST /api/v1/tutor/session                 # 创建会话
POST /api/v1/tutor/turn                    # 单轮对话（含 state machine 状态）

# AIGC（程序化优先）
POST /api/v1/content/generate
  body: {kg_node, modality: animation|diagram|widget|guide, level}
  resp: {content_id, pipeline: manim|mermaid|mdx, status, c2pa}

# 评测
POST /api/v1/eval/run                      # 触发 CI 评测
GET  /api/v1/eval/baseline                 # baseline 指标

# 隐私
POST /api/v1/user/unlearn                  # 触发机器遗忘
```

其余 v1 API（认证、群组、社交、游戏化、隐私）保留并兼容。

## 9. 评测体系 (Evaluation Harness) ★ v2.0 新增

无评测则无先进。所有模型变更必须经 CI 评测准入。

| 评测集 | 规模 | 指标 | 准入门槛 |
|---|---|---|---|
| KG 三元组抽取 | 500 条人工标注 | Precision / Recall / F1 | F1 ≥ 0.80 |
| 题目生成 | 200 题人工评分 | 事实正确率 / 难度落点准确率 / 干扰项有效性 | ≥ 0.90 / ≥ 0.70 / ≥ 0.60 |
| Tutor 对话 | 100 dialog | 苏格拉底度评分 / misconception 命中 / 不直接给答案率 | ≥ 4/5 / ≥ 0.7 / ≥ 0.95 |
| GraphRAG | 300 query | Faithfulness / Answer Relevancy (Ragas) / Citation 命中 | ≥ 0.85 / ≥ 0.80 / ≥ 0.90 |
| 推荐 | 历史日志重放 | NDCG@10 / mastery 增益 | 优于上一版本 |

工具：Ragas + Promptfoo + 自建 harness；评测集与版本绑定（DVC）。

## 10. 成本与延迟工程

| 策略 | 描述 |
|---|---|
| **模型路由** | 简单意图 → 7B 自托管；中等 → GPT-4o；推理/出题 → o3/R1 |
| **Prompt caching** | 长上下文教材 + 系统 prompt 全部缓存（Anthropic / Gemini 原生） |
| **请求合并** | 高频 mastery 更新、推荐刷新做批处理 |
| **冷热分层** | 热概念预生成内容入 Redis；冷概念按需生成 |
| **预算护栏** | 单用户日均 token 上限 + 每模型 cost cap，超限降级 |
| **观测** | Langfuse 全链路 trace + 单功能成本归因 |

目标：免费用户日均成本 < ¥0.50，付费用户 < ¥3.00。

## 11. 安全与合规

| 风险 | 防御 |
|---|---|
| **Prompt injection** | 学生输入分层隔离（system/user/document），injection classifier，敏感动作需二次确认 |
| **内容投毒** | 社区贡献池需投票门槛 + 自动事实核查 + KG 一致性校验 |
| **AIGC 误导** | 所有生成内容 c2pa 签名 + UI 显著标识 + 重要知识点人工抽检 |
| **未成年人保护** | 实名分级、时长限制、AIGC 标识、防沉迷；K12 学科类内容遵循"双减"红线（不提供校外培训属性服务） |
| **GDPR / 网安法** | 数据最小化、目的限定、可导出、可删除、机器遗忘证明 |
| **数据加密** | TLS 1.3 + AES-256 + 静态字段级加密（PII） |
| **审计** | 所有 LLM 调用 trace 30 天、合规事件不可篡改日志 |

## 12. 部署与可运维性

- **多区域**：合规数据本地化（中国 / 欧盟 / 北美 各自独立 stack）
- **多租户**：Postgres RLS + 命名空间隔离 + KG 租户标签
- **SLA/SLO**：API p95 < 800ms（非 LLM）、< 5s（LLM 流式首字）；可用性 99.9%
- **混沌工程**：定期演练 LLM provider 失效、KG 服务降级
- **Feature flags**：所有新模型 / 新 prompt 灰度 + 一键回滚

## 13. 实施路线图

| 阶段 | 周期 | 目标 |
|---|---|---|
| **M0 基线** | 4 周 | 评测集建立、GraphRAG MVP、单学科 KG 抽取通过 F1 0.80 |
| **M1 教学法** | 6 周 | BKT + IRT 上线，CAT 诊断、ZPD 选题、FSRS 复习 |
| **M2 Tutor** | 4 周 | 苏格拉底状态机 + injection 防御 + dialog 评测达标 |
| **M3 AIGC** | 6 周 | 程序化动画 + 干扰项库 + 双 LLM/求解器校验 |
| **M4 社区与合规** | 4 周 | 双轨内容池、机器遗忘、c2pa 标识、未成年人合规 |
| **M5 规模化** | 持续 | 多学科扩展、成本优化、混沌演练 |

## 14. 后续步骤

下一步基于本设计文档制定/更新详细实现计划，优先级：

1. **GraphRAG 化的 KG 构建管线**（更新 [2026-05-04-knowledge-graph-from-textbooks.md](../plans/2026-05-04-knowledge-graph-from-textbooks.md)：加入三层 schema、Leiden 社区检测、BGE-M3 消歧、structured outputs、评测集）
2. 教学法引擎（BKT/IRT/FSRS 服务）
3. Tutor 状态机与对话评测集
4. 程序化内容生成（Manim/Remotion）
5. 评测 harness 与 CI 准入

---

**文档状态**：v2.0 已批准；进入实现阶段前需先建立评测集 (M0)。
