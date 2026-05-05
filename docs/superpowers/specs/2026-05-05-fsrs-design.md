# FSRS 间隔重复系统规格说明书

## 1. 概述

### 目标
- 实现 FSRS-5 (Free Spaced Repetition Scheduler) 算法
- 结合概念依赖的遗忘加权管理
- 基于 IRT 能力估计自适应调整复习参数

### FSRS-5 核心思想

FSRS 是下一代间隔重复算法，相比 SM-18 有以下改进：
1. **稳定状态建模** - 将记忆建模为稳定的「稳定度」和波动的「 retrievability」
2. **预测稳定性** - 能预测未来不同间隔后的表现
3. **参数自适应** - 基于作答数据实时调整卡片参数

### 核心公式

**稳定度衰减:**
```
R(t) = exp((t - s) / (-9))
```
其中 R = retrievability (可回忆性), t = 时间, s = stability (稳定度)

**最优间隔预测:**
```
I(s, d) = s / (d - 1)
```
其中 I = interval, s = stability, d = desired retention (目标保留率)

---

## 2. 数据模型

### FSRSCard
```python
class FSRSCard(Base):
    """FSRS 卡片状态"""
    __tablename__ = "fsrs_cards"

    id: int
    user_id: int
    concept_id: int          # 关联概念
    state: str               # "new" | "learning" | "review" | "relearning"
    stability: float         # 稳定度 (分钟)
    difficulty: float        # 难度 (0-1)
    retrievability: float    # 当前可回忆性 (0-1)
    interval: float          # 当前间隔 (天)
    due: datetime            # 下次复习时间
    last_review: datetime
    last_result: str         # "again" | "hard" | "good" | "easy"
    reps: int                # 复习次数
    lapses: int              # 遗忘次数
    metadata: dict           # 额外参数
```

### FSRSReviewLog
```python
class FSRSReviewLog(Base):
    """FSRS 复习记录"""
    __tablename__ = "fsrs_review_logs"

    id: int
    card_id: int
    user_id: int
    reviewed_at: datetime
    rating: int              # 1=again, 2=hard, 3=good, 4=easy
    response_time: float     # 响应时间 (秒)
    stability_delta: float  # 稳定度变化
    new_interval: float     # 新间隔
    new_stability: float    # 新稳定度
    retention: float         # 实际保留率
```

### FSRSParameters
```python
class FSRSParameters:
    """FSRS 可调参数"""
    w: List[float]  # 权重数组 [10个参数]

    # 初始参数 (FSRS-5 默认值)
    DEFAULT_W = [
        0.4,    # w[0]: stability initial
        0.6,    # w[1]: difficulty initial
        2.4,    # w[2]: stability retention
        2.9,    # w[3]: difficulty retention
        4.9,    # w[4]: stability learning
        0.2,    # w[5]: stability relearning
        1.3,    # w[6]: difficulty relearning
        0.1,    # w[7]: stability again
        0.1,    # w[8]: stability hard
        0.1,    # w[9]: stability easy
    ]
```

---

## 3. 核心算法

### 3.1 卡片状态机

```
                    again
new ───────────────────────────> learning
                                    │
                               good │      hard
                                    v      v
review ─────────────────────────> review
   ^                               │
   │                               │ again
   │ good                          v
   └───────────────────────── relearning
```

**状态转移:**
- **new → learning**: 首次学习
- **learning → review**: 度过初始学习阶段
- **review → review**: 常规复习
- **review → relearning**: 遗忘后重新学习
- **relearning → review**: 重新学完

### 3.2 复习决策

```python
def schedule(card: FSRSCard, rating: int) -> dict:
    """
    rating: 1=again, 2=hard, 3=good, 4=easy

    返回:
    - next_interval: 下次间隔 (天)
    - next_stability: 下次稳定度
    - due: 下次到期时间
    - state: 新状态
    """

    if rating == 1:  # again
        card.lapses += 1
        card.state = "relearning"
        card.stability = card.stability * w[7]  # stability again
        card.difficulty = min(1.0, card.difficulty + w[6])

    elif rating == 2:  # hard
        card.stability = card.stability * w[8]  # stability hard
        card.interval = card.interval * w[3]

    elif rating == 3:  # good
        card.stability = card.stability * w[3]  # stability retention
        card.interval = card.stability / (1 - retention_target)  # I = s / (d - 1)

    elif rating == 4:  # easy
        card.stability = card.stability * w[9]  # stability easy
        card.interval = card.interval * w[4] * w[3]

    return {
        "next_interval": card.interval,
        "next_stability": card.stability,
        "due": now + timedelta(days=card.interval),
        "state": card.state
    }
```

### 3.3 间隔计算

```python
def compute_interval(stability: float, retention_target: float = 0.9) -> float:
    """计算最优复习间隔"""
    # I = s / (d - 1), 其中 d = -log10(1 - retention_target)
    # 对于 retention = 0.9, d = 1
    d = -math.log10(1 - retention_target)  # ≈ 1 for 90%
    interval = stability / d
    return max(1, interval)  # 最小1天
```

### 3.4 概念依赖加权

当多个概念相关时，遗忘会产生级联效应。

```python
def compute_concept_decay(concept_id: int, concept_graph: KnowledgeGraph) -> float:
    """
    计算概念依赖加权遗忘系数

    如果概念 A 依赖概念 B:
    - A 的遗忘会导致 B 的复习压力增加
    - B 的复习优先级提高
    """

    dependencies = concept_graph.get_dependencies(concept_id)
    decay = 1.0

    for dep in dependencies:
        # 依赖越深，加权越大
        depth = concept_graph.get_dependency_depth(concept_id, dep)
        decay *= (1 + 0.1 * depth)

    return decay
```

---

## 4. API 接口

### POST /api/v1/fsrs/cards
创建 FSRS 卡片

**Request:**
```json
{
  "user_id": 42,
  "concept_id": 123,
  "initial_stability": 10.0,  // 可选，默认使用 IRT θ 推断
  "initial_difficulty": 0.5   // 可选
}
```

### POST /api/v1/fsrs/review
提交复习结果

**Request:**
```json
{
  "card_id": 99,
  "rating": 3,
  "response_time": 12.5
}
```

**Response:**
```json
{
  "card_id": 99,
  "next_interval": 3.5,
  "next_due": "2026-05-08T10:00:00Z",
  "stability": 85.2,
  "retrievability": 0.91
}
```

### GET /api/v1/fsrs/due/{user_id}
获取待复习卡片

**Query params:**
- `limit`: int (默认 20)
- `concept_ids`: List[int] (可选，筛选概念)

**Response:**
```json
{
  "cards": [
    {
      "card_id": 99,
      "concept_id": 123,
      "state": "review",
      "due": "2026-05-05T14:00:00Z",
      "interval": 1.5,
      "stability": 45.0
    }
  ],
  "total_due": 15
}
```

### GET /api/v1/fsrs/stats/{user_id}
获取 FSRS 统计

**Response:**
```json
{
  "new_cards": 10,
  "learning": 5,
  "review": 50,
  "relearning": 2,
  "total_reviews_today": 34,
  "retention_today": 0.87
}
```

### DELETE /api/v1/fsrs/cards/{card_id}
删除卡片

---

## 5. 与 IRT 集成

```python
def estimate_initial_stability(theta: float, difficulty: float) -> float:
    """
    基于 IRT 能力估计和题目难度推断初始稳定度

    θ 高 + b 低 (容易题) → 高稳定度
    θ 低 + b 高 (难题) → 低稳定度
    """

    # 稳定度与 (θ - b) 成正比
    delta = theta - difficulty  # 假设 difficulty 标准化到 [-3, +3]

    # 映射到稳定度 (分钟)
    stability = 10 * math.exp(delta * 0.5)

    return max(1.0, min(stability, 1440))  # 限制在 1分钟到 24小时
```

---

## 6. 文件结构

```
backend/app/
├── models/
│   └── fsrs.py                  # FSRS 数据模型
├── services/
│   ├── fsrs_scheduler.py        # 调度器核心算法
│   └── fsrs_Concept_decay.py   # 概念依赖加权 (可选)
├── api/v1/routes/
│   └── fsrs.py                 # FSRS API 路由
└── core/
    └── config.py
```

---

## 7. 验收标准

1. **FSRS 算法正确性** - 使用 FSRS-5 参考实现验证
2. **间隔预测** - 给定相同 rating，输出稳定
3. **IRT 集成** - 能从 IRT θ 推断初始稳定度
4. **性能** - 1000 张卡片的调度 < 50ms
5. **状态机** - 所有状态转移正确

---

## 8. 参考文献

- FSRS-5 论文: https://github.com/open-spaced-repetition/fsrs4irl
- SM-18 对比基准