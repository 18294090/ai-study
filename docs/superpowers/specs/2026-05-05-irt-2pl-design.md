# IRT 2PL 难度标定系统规格说明书

## 1. 概述

### 目标
- 使用 Item Response Theory (IRT) 2-Parameter Logistic Model 对题库题目进行难度标定
- 根据学生作答数据使用 Maximum Likelihood Estimation (MLE) 或 Bayesian MCMC 估计题目参数 (a, b)
- 新题冷启动时使用 LLM 估计初始难度

### IRT 2PL 模型

```
P(θ) = 1 / (1 + exp(-a(θ - b)))

其中:
- θ: 学生能力值 (ability)
- a: 题目区分度 (discrimination) - 越高表示题目越能区分不同能力的学生
- b: 题目难度 (difficulty) - 能力多少才能有50%概率答对
```

### 能力值尺度
- 默认: θ ∈ [-3, +3], 以 0 为均值
- 通过锚题锚定到特定考试尺度 (如高考 500-700 分)

---

## 2. 数据模型

### IRTItemParams
```python
class IRTItemParams(Base):
    """IRT题目参数表"""
    __tablename__ = "irt_item_params"

    id: int
    question_id: int  # 外键到 questions 表
    model_type: str   # "2pl" | "3pl" (预留)
    a: float          # 区分度
    b: float          # 难度
    c: float = 0      # 猜测参数 (3PL only, 默认0)
    info: float       # Fisher Information (当前 θ 下的信息量)
    sample_size: int  # 标定所用的样本量
    calibrated_at: datetime
    status: str       # "calibrating" | "active" | "deprecated"
    metadata: dict    # 额外数据 (标准误, CI 等)
```

### IRTAbilityEstimate
```python
class IRTAbilityEstimate(Base):
    """学生能力估计表"""
    __tablename__ = "irt_ability_estimates"

    id: int
    user_id: int
    subject_id: int   # 科目维度分别估计
    theta: float      # 能力估计值
    se: float         # 标准误
    method: str       # "MLE" | "EAP" | "MAP"
    based_on: int     # 基于作答次数
    estimated_at: datetime
```

### IRTCalibrationSession
```python
class IRTCalibrationSession(Base):
    """标定会话 (批量标定一次)"""
    __tablename__ = "irt_calibration_sessions"

    id: int
    subject_id: int
    question_ids: List[int]
    method: str          # "MLE" | "BME" (Bayesian)
    iterations: int
    converged: bool
    final_loglik: float
    created_at: datetime
```

### ResponseRecord
```python
class ResponseRecord(Base):
    """作答记录 (用于标定)"""
    __tablename__ = "irt_response_records"

    id: int
    question_id: int
    user_id: int
    correct: bool
    response_time: float  # 秒
    attempt: int         # 第几次作答
    recorded_at: datetime
```

---

## 3. 核心算法

### 3.1 题目参数估计 (Calibration)

**方法: Joint Maximum Likelihood Estimation (JMLE)**

对每道题目，独立估计 a 和 b。

**似然函数:**
```
L(a, b | responses) = ∏ P(θ_i)^{correct_i} * (1 - P(θ_i))^{1-correct_i}
```

其中 P(θ) = 1 / (1 + exp(-a(θ - b)))

**约束:**
- a ∈ [0.3, 2.5] (防止过拟合)
- b ∈ [-3, +3]
- 至少需要 30 条有效作答记录才能进行标定

**迭代算法: Newton-Raphson**

```
∂logL/∂b = Σ (correct_i - P_i) * a
∂logL/∂a = Σ (correct_i - P_i) * (θ_i - b) * a

迭代直到收敛: |Δa| < 0.001 and |Δb| < 0.001
```

**预设初值:**
- a₀ = 1.0
- b₀ = 0.0 (或基于答对率估计: b₀ = Φ⁻¹(accuracy))

### 3.2 学生能力估计 (Ability Estimation)

**方法: Expected A Posteriori (EAP)**

先验: θ ~ N(0, 1)

后验:
```
P(θ | responses) ∝ N(θ; 0, 1) * ∏ P(θ)
```

数值积分求期望:
```
E[θ] = ∫ θ * P(θ | responses) dθ / ∫ P(θ | responses) dθ
```

**网格点:** θ ∈ {-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3}, 步长 0.5

### 3.3 新题冷启动 (LLM Estimation)

当某题作答记录 < 10 条时，使用 LLM 估计初始 b 值。

**Prompt:**
```
你是一个题目难度评估专家。请评估以下题目的难度。

题目: {question_content}
选项: {options}
知识点: {knowledge_points}

难度等级:
- 容易 (b ≈ -1.5): 基础知识理解
- 中等 (b ≈ 0): 综合运用
- 困难 (b ≈ +1.5): 深度推理/创新

请给出:
1. 估计的难度值 b (范围 [-3, +3])
2. 置信度 (低/中/高)
3. 理由
```

**输出解析:** 从 LLM 响应中提取 b 值，存储并标记为 "llm_estimated"

---

## 4. API 接口

### POST /api/v1/irt/calibrate
批量标定题目参数

**Request:**
```json
{
  "question_ids": [1, 2, 3, ...],
  "method": "MLE",
  "min_responses": 30
}
```

**Response:**
```json
{
  "session_id": 123,
  "calibrated": 45,
  "skipped": 5,
  "details": [
    {"question_id": 1, "a": 1.23, "b": 0.45, "se_a": 0.12, "se_b": 0.08},
    ...
  ]
}
```

### GET /api/v1/irt/estimate/{user_id}
估计学生能力

**Query params:**
- `subject_id`: int (required)

**Response:**
```json
{
  "user_id": 42,
  "subject_id": 1,
  "theta": 0.85,
  "se": 0.32,
  "based_on": 156,
  "method": "EAP"
}
```

### POST /api/v1/irt/estimate/ability
更新学生能力估计 (基于最新作答)

**Request:**
```json
{
  "user_id": 42,
  "subject_id": 1,
  "question_id": 99,
  "correct": true,
  "response_time": 45.2
}
```

### GET /api/v1/irt/items/{question_id}
获取题目 IRT 参数

**Response:**
```json
{
  "question_id": 99,
  "model_type": "2pl",
  "a": 1.23,
  "b": 0.45,
  "info": 0.67,
  "status": "active",
  "sample_size": 234
}
```

### POST /api/v1/irt/estimate/from-llm
LLM 冷启动估计 (新题)

**Request:**
```json
{
  "question_id": 999,
  "question_content": "...",
  "options": {...},
  "knowledge_points": ["二次函数", "函数图像"]
}
```

---

## 5. 文件结构

```
backend/app/
├── models/
│   └── irt.py                    # IRT 数据模型
├── services/
│   ├── irt_calibration.py        # 题目参数标定服务
│   └── irt_ability.py            # 学生能力估计服务
├── api/v1/routes/
│   └── irt.py                    # IRT API 路由
└── core/
    └── config.py                 # 配置 (LLM 用于冷启动)
```

---

## 6. 配置

```yaml
# backend/app/kg/config.yaml

irt:
  default_method: "EAP"           # 能力估计方法
  min_responses_calibrate: 30    # 最少作答数才标定
  min_responses_ability: 5        # 最少作答数才估计能力
  ability_grid: [-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3]
  priors:
    a_mean: 1.0
    a_std: 0.3
  constraints:
    a_min: 0.3
    a_max: 2.5
    b_min: -3.0
    b_max: 3.0
  llm_estimation:
    enabled: true
    min_responses: 10             # 少于10条记录时启用LLM估计
    model: "gpt-4o"
```

---

## 7. 验收标准

1. **标定正确性:** 已知 θ 和作答数据，能恢复出题目参数
2. **能力估计一致性:** 相同作答记录，多次估计结果稳定
3. **冷启动质量:** LLM 估计的 b 值与实际标定结果偏差 < 0.5
4. **性能:** 单题标定 < 100ms (无 LLM 调用)
5. **可挂起:** 大量题目标定可分批进行

---

## 8. 与现有系统集成

- **题目表:** `questions.difficulty` 字段保留旧值，IRT 参数存储在新表
- **BKT:** IRT θ 可作为 BKT 初始 p 的参考 (但不直接混用)
- **推荐:** 推荐时同时考虑题目难度 (b) 和学生能力 (θ)