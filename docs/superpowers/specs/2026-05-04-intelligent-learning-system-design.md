# LearnHub - 智慧学习系统设计文档

> **Date:** 2026-05-04
> **Status:** Approved
> **Version:** 1.2（新增 AIGC 试题生成）

## 1. 核心理念

**去中心化的学习社区** —— 每个用户既是学习者，也可以随时成为组织者。知识共享、学习协作、成就激励全部围绕用户展开。

## 2. 核心设计原则

| 原则 | 描述 |
|------|------|
| **用户中心** | 每个用户拥有完整数据主权，可导出、删除、撤回授权 |
| **角色平等** | 学习者与组织者随时切换，无固定身份绑定 |
| **知识共享** | 群组内知识共建，去中心化无权威教师 |
| **数据贡献** | 用户同意后数据用于AI训练优化（可随时撤回） |
| **合规优先** | GDPR、中国网络安全法、未成年人保护全面合规 |

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        云端服务层 (SaaS)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  知识图谱 │  │   题库    │  │ 学习路径  │  │   社交   │        │
│  │  服务    │  │   服务    │  │   服务    │  │   服务   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └─────────────┴─────────────┴─────────────┘              │
│                           │                                    │
│  ┌────────────────────────┼─────────────────────────────┐    │
│  │              内容生成服务 (AIGC)                       │    │
│  │  • 视频生成   • 图片生成   • 文字内容生成             │    │
│  └────────────────────────┬─────────────────────────────┘    │
│                           │                                    │
│  ┌────────────────────────┼─────────────────────────────┐    │
│  │              游戏化 + 成就系统                          │    │
│  └────────────────────────┬─────────────────────────────┘    │
│                           │                                    │
│  ┌────────────────────────┼─────────────────────────────┐    │
│  │                 数据层 (统一云端)                       │    │
│  │  • PostgreSQL (核心数据)                               │    │
│  │  • Neo4j (知识图谱)                                     │    │
│  │  • Redis (缓存)                                        │    │
│  │  • S3 (静态资源/生成的视频/图片)                       │    │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │
┌────────▼────────┐
│      用户       │
│  学习者 ↔ 组织者 │
│  (随时切换)     │
└─────────────────┘
```

## 4. 技术栈

| 组件 | 技术选型 |
|------|----------|
| **文档解析** | MinerU（PDF/扫描件 → 结构化文本） |
| **知识图谱存储** | Neo4j |
| **核心数据库** | PostgreSQL |
| **缓存** | Redis |
| **对象存储** | S3（静态资源/图片/视频） |
| **AI 抽取** | GPT-4o / Claude-3.5 |
| **Agent 框架** | DeerFlow 2.0 |
| **后端框架** | FastAPI / LangGraph |
| **前端** | React + Tailwind |
| **部署** | Docker + Kubernetes (云端) |
| **视频生成** | Sora / Pika / Runway / 自研视频生成模型 |
| **图片生成** | DALL-E / Midjourney / Stable Diffusion |
| **文字生成** | GPT-4o / Claude / 专项微调模型 |
| **内容审核** | AI 自动化审核 + 人工复核机制 |

## 5. 用户角色设计

| 角色 | 权限 |
|------|------|
| **学习者（默认）** | 学习、刷题、查看知识图谱、参与群组、社交、查看成就 |
| **组织者（按需切换）** | 创建群组、分享知识、组织学习活动、发起挑战、查看群组统计 |

**切换机制**：用户点击按钮即可切换，无需审批

## 6. 核心功能模块

### 6.1 知识图谱服务

| 功能 | 描述 |
|------|------|
| **教材解析** | MinerU 解析 PDF/扫描件，保留章节、公式、表格结构 |
| **知识抽取** | LLM 识别实体（概念/人物/事件/公式/作品等）和关系（is_a/part_of/causes等） |
| **图谱存储** | Neo4j 存储知识三元组，支持属性（置信度/来源/描述） |
| **图谱查询** | 知识点检索、路径分析、关联推荐 |
| **可视化** | 交互式图谱展示，支持筛选和下钻 |

**知识图谱 Schema：**

```
Entity Types: concept, person, event, location, formula, work, time
Relation Types: is_a, part_of, causes, relates_to, applies_to, before, after, similar_to, defined_by, example_of
```

### 6.2 题库系统

| 功能 | 描述 |
|------|------|
| **试卷导入** | 支持 PDF/图片/Word/纯文本多格式输入 |
| **智能解析** | MinerU + OCR 识别题目、选项、答案 |
| **自动标注** | LLM 自动标注：知识点关联、难度(1-5)、题型、能力维度(布鲁姆) |
| **智能组卷** | 根据目标知识点/难度/能力维度自动生成试卷 |
| **题目检索** | 按知识点/难度/能力等多维度检索 |
| **试题生成 (AIGC)** | 基于知识图谱自动生成新题目（选择/填空/解答/证明题） |
| **题目改编** | 根据学习者水平自动改编题目难度 |
| **答案解析生成** | 自动生成题目答案与详细解析 |

**试题生成流程：**
```
知识点 → 学习者水平分析 → 题目类型选择 → AIGC 生成 → 质量校验 → 入库
```

### 6.3 学习路径服务

| 功能 | 描述 |
|------|------|
| **学情诊断** | 综合考试评估 + 实时答题分析 + 知识图谱推理 |
| **薄弱点定位** | 基于知识图谱的掌握关系推断 |
| **路径规划** | AI 根据认知科学原理规划最优学习顺序 |
| **内容推荐** | 自适应推送视频/图文/互动等多模态内容 |
| **进度追踪** | 实时更新学习进度和掌握度 |

### 6.4 去中心化群组

| 功能 | 描述 |
|------|------|
| **创建群组** | 任何用户可创建，设置群组名称/描述/可见性 |
| **加入群组** | 搜索加入或邀请链接加入 |
| **知识共享** | 群组成员共建知识库，上传资料和笔记 |
| **学习活动** | 组织者发起学习任务、挑战、答疑 |
| **群组排行** | 群组内学习贡献/活跃度排行 |

### 6.5 社交学习

| 功能 | 描述 |
|------|------|
| **问答社区** | 发布问题，悬赏积分，成员解答 |
| **讨论区** | 话题讨论，帖子/评论 |
| **进度对比** | 与好友/群组成员对比学习进度 |
| **学习搭档** | 基于共同兴趣/目标匹配学习搭档 |

### 6.6 游戏化系统

| 功能 | 描述 |
|------|------|
| **成就徽章** | 达成里程碑获得徽章（首次完成/连续学习/知识贡献等） |
| **学习积分** | 完成任务/回答问题/分享知识获得积分 |
| **排行榜** | 全站/群组/好友排行（日/周/月/总榜） |
| **连续学习** | streaks 显示连续学习天数，断裂提醒 |
| **里程碑奖励** | 达成目标获得奖励（徽章/积分/特权） |

### 6.7 自适应内容

| 功能 | 描述 |
|------|------|
| **多模态推送** | 根据用户偏好推送视频/图文/互动内容 |
| **难度递进** | 支架式教学，内容难度逐步提升 |
| **跨学科关联** | 主动展示知识点在其他学科的应用 |
| **遗忘曲线** | 根据艾宾浩斯遗忘曲线安排复习 |

### 6.8 内容生成服务 (AIGC)

基于知识图谱和用户学情，自动生成多模态学习资料。

| 功能 | 描述 | 技术方案 |
|------|------|----------|
| **视频生成** | 根据知识点自动生成教学视频 | Sora / Pika / Runway / 自研视频生成 |
| **图片生成** | 生成知识点插图、流程图、示意图 | DALL-E / Midjourney / Stable Diffusion |
| **文字生成** | 生成知识点讲解、案例分析、学习指南 | GPT-4o / Claude / 专项微调模型 |
| **互动内容** | 生成测验、填空、排序等互动练习 | 规则引擎 + LLM |
| **个性化适配** | 根据学习者水平和偏好调整内容形式 | 学情分析 + 内容适配引擎 |

**内容生成流程：**
```
知识图谱中的知识点
       ↓
   学情诊断（学习者当前水平）
       ↓
   内容规划（选择合适的媒体形式）
       ↓
   AIGC 生成（视频/图片/文字/互动）
       ↓
   质量审核（AI + 人工审核）
       ↓
   内容发布（进入学习推荐池）
```

**支持的内容类型：**

| 类型 | 示例 |
|------|------|
| **教学视频** | "三角函数"知识点 → 3分钟动画讲解视频 |
| **知识点图解** | "光合作用" → 细胞结构示意图 + 流程图 |
| **学习指南** | "辛亥革命" → 时间轴 + 关键人物 + 影响分析 |
| **互动测验** | "二次方程" → 选择/填空/解答互动练习题 |
| **案例分析** | "经济学原理" → 真实案例 + 讨论问题 |

**质量控制：**
- AI 生成内容需经过准确性校验
- 重要知识点支持人工审核流程
- 用户可反馈内容质量，帮助持续优化

### 6.9 监控与报告

| 功能 | 描述 |
|------|------|
| **学习报告** | 周报/月报自动生成，推送至用户 |
| **数据导出** | 用户可导出自己的所有数据（合规要求） |
| **隐私控制** | 数据共享范围、授权管理 |

## 7. 数据模型

### 7.1 核心实体

```python
User:
  - id: str
  - email: str
  - name: str
  - password_hash: str
  - role: str (learner/organizer/both)
  - created_at: datetime
  - privacy_settings: dict
  - consent_for_ai_training: bool

KnowledgeGraph:
  - id: str
  - source: str (教材名称)
  - subject: str (science/arts)
  - nodes: List[Entity]
  - edges: List[Relation]

Entity:
  - id: str
  - name: str
  - type: EntityType
  - description: str
  - source: str
  - confidence: float

Relation:
  - subject_id: str
  - predicate: RelationType
  - object_id: str
  - confidence: float
  - source: str

Question:
  - id: str
  - content: str
  - options: List[str] (for choice)
  - answer: str
  - explanation: str
  - knowledge_points: List[str]
  - difficulty: int (1-5)
  - question_type: str (choice/fill/answer/proof)
  - ability_level: str (remember/understand/apply/analyze/evaluate/create)
  - source: str

QuestionBank:
  - id: str
  - name: str
  - questions: List[Question]
  - created_by: str (user_id)

Group:
  - id: str
  - name: str
  - description: str
  - created_by: str (user_id)
  - members: List[str] (user_ids)
  - visibility: str (public/private)
  - shared_knowledge: List[str] (kg_ids)

LearningPath:
  - id: str
  - user_id: str
  - diagnosis: dict
  - recommendations: List[dict]
  - progress: dict
  - achievements: List[str]

Gamification:
  - user_id: str
  - points: int
  - streak_days: int
  - achievements: List[str]
  - leaderboard_position: int

Content:
  - id: str
  - knowledge_point: str
  - content_type: str (video/image/text/interactive)
  - url: str (S3 storage URL)
  - generated_by: str (user_id / AI)
  - target_level: str (beginner/intermediate/advanced)
  - status: str (generating/ready/archived)
  - quality_score: float
  - usage_count: int
  - created_at: datetime
```

## 8. API 设计

### 8.1 认证

```
POST /api/v1/auth/register          # 注册
POST /api/v1/auth/login             # 登录
POST /api/v1/auth/logout            # 登出
POST /api/v1/auth/data-export       # 导出用户数据
POST /api/v1/auth/consent           # AI训练授权同意
DELETE /api/v1/auth/consent         # 撤回AI训练授权
```

### 8.2 知识图谱

```
POST /api/v1/knowledge-graph/build    # 教材→知识图谱
GET  /api/v1/knowledge-graph/:id     # 获取图谱
GET  /api/v1/knowledge-graph/query   # 查询知识点
GET  /api/v1/knowledge-graph/visualize/:id  # 可视化
```

### 8.3 题库

```
POST /api/v1/question-bank/import     # 导入试卷
GET  /api/v1/question-bank/:id        # 获取题库
GET  /api/v1/questions                # 搜索题目
GET  /api/v1/questions/:id             # 题目详情
POST /api/v1/exam/generate            # 智能组卷
POST /api/v1/exam/submit              # 提交答案
POST /api/v1/questions/generate        # AIGC 生成试题
  - body: { knowledge_point, question_type, difficulty, count }
  - response: { question_ids[] }
POST /api/v1/questions/:id/regenerate # 题目改编
```

### 8.4 学习

```
POST /api/v1/learning/diagnosis        # 学情诊断
GET  /api/v1/learning/path             # 获取学习路径
GET  /api/v1/learning/progress         # 学习进度
GET  /api/v1/learning/recommendations   # 内容推荐
```

### 8.5 内容生成 (AIGC)

```
POST /api/v1/content/generate          # 生成学习资料
  - body: { knowledge_point, content_type: video/image/text/interactive, target_level }
  - response: { content_id, status, estimated_time }

GET  /api/v1/content/:id               # 获取生成的内容
GET  /api/v1/content/templates         # 获取内容模板
POST /api/v1/content/:id/feedback      # 用户反馈内容质量
GET  /api/v1/content/pool               # 内容池（可搜索）
```

### 8.6 群组（去中心化）

```
POST /api/v1/groups/create             # 创建群组
GET  /api/v1/groups                    # 搜索群组
POST /api/v1/groups/:id/join           # 加入群组
POST /api/v1/groups/:id/leave          # 离开群组
GET  /api/v1/groups/:id                # 群组详情
POST /api/v1/groups/:id/share-knowledge # 共享知识
GET  /api/v1/groups/:id/members        # 成员列表
```

### 8.7 社交

```
POST /api/v1/discussions               # 发布讨论
GET  /api/v1/discussions/:id           # 讨论详情
POST /api/v1/discussions/:id/reply     # 回复
GET  /api/v1/progress-comparison       # 进度对比
GET  /api/v1/learning-partners         # 学习搭档匹配
```

### 8.8 游戏化

```
GET  /api/v1/achievements              # 成就列表
GET  /api/v1/achievements/:id          # 成就详情
GET  /api/v1/leaderboard               # 排行榜
GET  /api/v1/gamification/stats         # 用户游戏化数据
POST /api/v1/gamification/streak       # 更新streak
```

### 8.9 数据与隐私

```
GET  /api/v1/user/profile              # 用户资料
PUT  /api/v1/user/profile              # 更新资料
GET  /api/v1/user/privacy-settings     # 隐私设置
PUT  /api/v1/user/privacy-settings     # 更新隐私设置
GET  /api/v1/user/data                # 获取所有数据
DELETE /api/v1/user/data               # 删除所有数据
```

## 9. 合规设计

| 合规要求 | 实现方式 |
|---------|---------|
| **数据加密** | 传输 TLS 1.3，存储 AES-256 |
| **用户主权** | 数据可导出、可删除、可撤回授权 |
| **AI训练授权** | 用户同意后数据用于模型优化，可随时撤回 |
| **GDPR** | 数据最小化、删除权、便携性、同意管理 |
| **网络安全法** | 数据分类分级、加密传输、日志审计 |
| **未成年人保护** | 实名认证、时长限制、内容过滤、家长监控接口 |

## 10. 部署

- **架构**：纯云端 SaaS，多租户
- **容器化**：Docker + Kubernetes
- **区域**：支持多区域部署，合规数据本地化
- **监控**：日志审计、异常检测、SLA 保障

## 11. 后续步骤

下一步将基于本设计文档制定详细的实现计划，涵盖：
- 知识图谱构建（基于 DeerFlow + MinerU）
- 题库生成系统
- 学习路径引擎
- 游戏化与社交功能
- 前端实现

---

**文档状态**：已批准，可进入实现阶段