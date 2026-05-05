# Expert Reviewer 知识冲突仲裁系统规格说明书

## 1. 概述

### 目标
- 实现 KG (Knowledge Graph) 冲突检测与仲裁队列
- 严重性 ≥ 0.5 的冲突进入人工审核流程
- 支持多专家协作评审

### 冲突来源
1. **图谱内冲突** - 同一关系在不同来源中陈述矛盾
2. **时间冲突** - 事实随时间变化但未标记
3. **粒度冲突** - 抽象层次不一致
4. **命名冲突** - 同义/近义实体未对齐

---

## 2. 数据模型

### KGConflict
```python
class KGConflict(Base):
    """知识冲突记录"""
    __tablename__ = "kg_conflicts"

    id: int
    conflict_type: str      # "contradiction" | "temporal" | "granularity" | "naming"
    severity: float         # 严重性 [0, 1]
    entity_ids: List[int]   # 涉及实体
    statement_a: str        # 冲突陈述 A
    statement_b: str        # 冲突陈述 B
    source_a: str           # 来源 A
    source_b: str           # 来源 B
    context: dict           # 上下文信息
    status: str             # "pending" | "reviewing" | "resolved" | "rejected"
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution: Optional[str]  # 解决方式
    resolver_id: Optional[int] # 审核人
```

### ExpertReview
```python
class ExpertReview(Base):
    """专家评审记录"""
    __tablename__ = "expert_reviews"

    id: int
    conflict_id: int        # 外键
    expert_id: int          # 外键 (用户)
    recommendation: str     # "accept_a" | "accept_b" | "merge" | "reject"
    confidence: float       # 置信度 [0, 1]
    reasoning: str          # 理由
    voted_at: datetime
```

### ConflictQueue
```python
class ConflictQueue(Base):
    """冲突队列管理"""
    __tablename__ = "kg_conflict_queue"

    id: int
    priority: int            # 优先级 (1=最高)
    conflict_id: int
    assigned_to: Optional[int]  # 指定审核人
    due_date: datetime
    notifications_sent: int
```

---

## 3. 核心算法

### 3.1 冲突严重性计算

```python
def compute_severity(conflict: ConflictEvidence) -> float:
    """
    计算冲突严重性分数 [0, 1]

    因素:
    - 实体重要性 (entity importance)
    - 来源可靠性差异 (source reliability delta)
    - 陈述置信度差异 (confidence delta)
    - 上下文覆盖度
    """

    score = 0.0

    # 实体重要性权重
    entity_importance = get_entity_importance(conflict.entity_ids)
    score += entity_importance * 0.3

    # 来源可靠性
    reliability_delta = abs(source_a.reliability - source_b.reliability)
    score += reliability_delta * 0.3

    # 置信度差异
    confidence_delta = abs(confidence_a - confidence_b)
    score += confidence_delta * 0.25

    # 上下文覆盖
    context_coverage = compute_context_overlap(conflict.context_a, conflict.context_b)
    score += (1 - context_coverage) * 0.15

    return min(1.0, score)


def should_escalate(severity: float) -> bool:
    """判断是否需要人工审核"""
    return severity >= 0.5
```

### 3.2 自动解决规则

```python
class ConflictResolver:
    """冲突自动解决器"""

    RULES = [
        ("source_reliability", self._resolve_by_reliability),
        ("temporal_precedence", self._resolve_by_recency),
        ("granularity_hierarchy", self._resolve_by_granularity),
    ]

    def try_auto_resolve(self, conflict: KGConflict) -> Optional[Resolution]:
        """
        尝试自动解决冲突

        返回 Resolution 或 None (需要人工)
        """

        # 规则1: 高可靠性来源优于低可靠性
        if self._resolve_by_reliability(conflict):
            return Resolution(winner="source_a", confidence=0.9)

        # 规则2: 新近事实优于旧事实 (时间冲突)
        if conflict.conflict_type == "temporal":
            if self._resolve_by_recency(conflict):
                return Resolution(winner="newer", confidence=0.8)

        # 规则3: 细粒度优于粗粒度
        if conflict.conflict_type == "granularity":
            if self._resolve_by_granularity(conflict):
                return Resolution(winner="finer", confidence=0.7)

        return None  # 需要人工审核
```

### 3.3 多专家共识

```python
def compute_consensus(reviews: List[ExpertReview]) -> ConsensusResult:
    """
    计算专家评审共识

    返回:
    - recommendation: 最终建议
    - agreement_score: 一致性分数 [0, 1]
    - confidence: 置信度
    """

    recommendations = [r.recommendation for r in reviews]

    # 多数投票
    vote_counts = Counter(recommendations)
    majority = vote_counts.most_common(1)[0]

    agreement = majority[1] / len(reviews)  # 一致性比例

    # 置信度 = 一致性 * 平均专家置信度
    avg_confidence = sum(r.confidence for r in reviews) / len(reviews)
    confidence = agreement * avg_confidence

    return ConsensusResult(
        recommendation=majority[0],
        agreement_score=agreement,
        confidence=confidence
    )
```

---

## 4. API 接口

### GET /api/v1/expert-reviewer/conflicts
获取冲突队列

**Query params:**
- `status`: "pending" | "reviewing" | "resolved" | "rejected"
- `min_severity`: float (默认 0.0)
- `limit`: int (默认 20)
- `offset`: int (默认 0)

**Response:**
```json
{
  "conflicts": [
    {
      "id": 123,
      "conflict_type": "contradiction",
      "severity": 0.72,
      "entity_ids": [1, 2],
      "statement_a": "光速是299792458 m/s",
      "statement_b": "光速是300000000 m/s",
      "status": "pending",
      "created_at": "2026-05-05T10:00:00Z"
    }
  ],
  "total": 45,
  "pending_count": 30
}
```

### GET /api/v1/expert-reviewer/conflicts/{conflict_id}
获取冲突详情

### POST /api/v1/expert-reviewer/conflicts/{conflict_id}/resolve
解决冲突

**Request:**
```json
{
  "resolution": "accepted_a",
  "reasoning": "source_a 有更高的可靠性评分"
}
```

### POST /api/v1/expert-reviewer/reviews
提交专家评审

**Request:**
```json
{
  "conflict_id": 123,
  "expert_id": 42,
  "recommendation": "merge",
  "confidence": 0.85,
  "reasoning": "两条陈述在不同粒度上都正确，可以共存"
}
```

### GET /api/v1/expert-reviewer/stats
获取仲裁统计

**Response:**
```json
{
  "total_conflicts": 100,
  "pending": 30,
  "resolved": 65,
  "rejected": 5,
  "auto_resolved": 20,
  "avg_resolution_time_hours": 48,
  "consensus_rate": 0.78
}
```

---

## 5. 与 KG 集成

```python
# 在知识图谱更新时检测冲突
class KGConflictDetector:
    """冲突检测器"""

    def detect_on_update(self, entity_id: int, new_statement: Statement) -> List[KGConflict]:
        """
        当 KG 更新时检测冲突

        1. 查找相关实体
        2. 对比现有陈述
        3. 计算严重性
        4. 自动解决或进入队列
        """

        related = self.kg.find_related_entities(entity_id)

        conflicts = []
        for rel_entity in related:
            existing = self.kg.get_statement(rel_entity)

            if self._is_contradiction(new_statement, existing):
                severity = compute_severity(new_statement, existing)

                if severity >= 0.5:
                    conflict = self._create_conflict(new_statement, existing, severity)
                    conflicts.append(conflict)
                else:
                    self._auto_resolve(new_statement, existing)

        return conflicts
```

---

## 6. 文件结构

```
backend/app/
├── models/
│   └── expert_reviewer.py      # 冲突/评审数据模型
├── services/
│   ├── conflict_detector.py    # 冲突检测
│   ├── conflict_resolver.py    # 自动解决
│   └── consensus_engine.py     # 共识计算
├── api/v1/routes/
│   └── expert_reviewer.py      # API 路由
└── core/
    └── config.py
```

---

## 7. 验收标准

1. **冲突检测** - 新增冲突能正确计算严重性
2. **自动解决** - 严重性 < 0.5 的冲突能自动解决
3. **人工队列** - 严重性 ≥ 0.5 进入人工审核
4. **共识计算** - 多专家评审能正确汇总
5. **集成** - 与 KG 更新流程集成

---

## 8. 与系统其他模块关系

```
KG 更新 → ConflictDetector → [自动解决 | 人工队列]
                                    ↓
                            ExpertReviewer
                                    ↓
                            ConsensusEngine → Resolution
```

- **IRT**: 用于评估来源可靠性
- **GraphRAG**: 用于检索冲突上下文
- **Tutor**: 用于向学生解释冲突解决结果