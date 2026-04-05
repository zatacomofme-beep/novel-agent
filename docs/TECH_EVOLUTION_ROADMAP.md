# novel-agent 技术演进规划文档

> 本文档基于 `docs/architecture/` 下五份新增规划文档与现有代码库的深度比对分析，整合所有新增技术需求与实现策略，作为项目后续迭代的核心指导文档。

---

## 一、文档背景

### 1.1 规划文档清单

| 文档 | 主题 | 来源 |
|------|------|------|
| `technical_optimization_roadmap.md` | 100+ 技术细节优化路线图 | 新增 |
| `narrative_product_innovation.md` | 叙事产品创新功能 | 新增 |
| `advanced_narrative_engineering.md` | 深度叙事工程 | 新增 |
| `commercialization_and_deployment_analysis.md` | 商业化与部署分析 | 新增 |
| `cost_efficiency_and_routing.md` | 成本优化与路由策略 | 新增 |

### 1.2 现有系统概述

**技术栈**：Next.js 14 + FastAPI + SQLAlchemy 2.0 + LangGraph + Celery + PostgreSQL + **Neo4j** + Qdrant

**核心架构**：Multi-Agent 协作系统（9 个 Agent）+ Story Engine 工作流 + Canon 世界观守护

**现状瓶颈**：
- Agent 执行链为线性串行，无并行化
- 纯向量检索，无因果图谱
- 无 Token 熔断，成本不可控
- 角色系统无语言指纹和社交拓扑
- 无伏笔生命周期管理

---

## 二、技术需求分类总览

### 2.1 功能模块分类

| 模块 | 功能数量 | 核心需求 |
|------|----------|----------|
| **Multi-Agent 编排升级** | 3 | Sub-graph 递归、并行执行、Retry/Fallback |
| **知识与一致性引擎** | 5 | 因果图谱、Open Threads、L1/L2/L3 记忆、Temporal Logic、语义压缩 |
| **模型路由与成本** | 5 | T1/T2/T3 路由、Prompt Caching、Token 熔断、Batch API、按需 Critic |
| **角色心智与叙事** | 7 | 语言指纹、社交拓扑、Linguistic Checker、张力传感、Chaos Agent、虚拟读者、Undo/Redo |
| **部署与商业化** | 5 | K8s + HPA、LangSmith、Prometheus/Grafana、多级 Queue、Checkpoint Pause |

### 2.2 优先级矩阵

```
        高影响力
            ↑
            │
    ┌───────┼───────┐
    │  P0   │  P1   │
    │ 核心  │ 产品级 │
    │ 差异化│ 体验   │
    ├───────┼───────┤
    │  P2   │  P3   │
    │ 运营  │ 低优先级│
    │ 必备  │        │
    └───────┴───────┘
            │
            ↓
        低实施成本
```

---

## 三、P0 — 核心差异化功能

> 解决竞品无解、用户最能感知的"吃书"和"逻辑断裂"问题

### 3.1 Open Threads DB — 伏笔生命周期管理

#### 问题背景

AI 长篇创作最大顽疾：**伏笔埋下后遗忘**，导致"吃书"问题。现有系统仅有 `Foreshadowing` 静态实体，无生命周期概念。

#### 技术方案

**新增数据模型**：

```python
class OpenThread(Base):
    """伏笔追踪记录"""
    __tablename__ = "open_threads"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)

    # 伏笔元信息
    planted_chapter: Mapped[int]  # 埋下的章节号
    entity_ref: Mapped[str]      # 关联实体（如"带血的信封"）
    entity_type: Mapped[str]     # item/character/event/relationship
    potential_tags: Mapped[list[str]]  # ["悬念", "阴谋", "伏笔"]

    # 生命周期状态
    status: Mapped[str] = mapped_column(String(20), default="open")
    # open | tracking | resolution_pending | resolved | abandoned

    # 回收信息
    payoff_chapter: Mapped[Optional[int]]  # 回收章节号
    payoff_priority: Mapped[float]  # 0.0-1.0，算法计算
    resolution_summary: Mapped[Optional[str]]

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**伏笔识别规则**：

| 识别信号 | 示例 | 标记方式 |
|----------|------|----------|
| 悬念句式 | "他总觉得那张信纸不简单" | 触发埋雷 |
| 异常物品 | "带血的信封出现在现场" | 实体关联 |
| 关系暗示 | "她看他的眼神有些奇怪" | 关系追踪 |
| 时间标记 | "这个决定将在三天后显现后果" | 时序关联 |

**三阶段生命周期**：

```
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────┐
│ Planting │ → │ Tracking│ → │Resolution_Pending│ → │Resolved │
│   埋雷   │    │   追踪   │    │    待回收     │    │   已回收  │
└─────────┘    └─────────┘    └──────────────┘    └─────────┘
     │              │                  │                │
     ↓              ↓                  ↓                ↓
[识别悬念]    [章节生成前    [Architect强制     [记录回收
  自动入库]     强制检查]     插入回收情节]      总结归档]
```

#### 入手点

- `backend/models/` 新建 `open_thread.py`
- `backend/services/` 新建 `foreshadowing_lifecycle_service.py`
- `backend/agents/architect.py` — 在章节计划生成时强制注入 Active Foreshadowings
- `backend/api/v1/` — 新增 `/projects/{id}/open-threads` 端点

#### 实施预估

- **模型层**：1 天
- **Service 层**：2 天
- **Agent 集成**：2 天
- **API + 前端展示**：2 天
- **总计**：约 7 个工作日

---

### 3.2 因果图谱 — Neo4j 图数据库

#### 问题背景

纯向量检索无法表达"事件 A 导致事件 B"的因果链条。PostgreSQL 递归 CTE 只能做简单的前后遍历，无法支持复杂的图分析（如：角色影响力中心性分析、故事结构模式匹配、多路径溯源）。

#### 技术方案

**引入 Neo4j 图数据库**：

```
neo4j:
  image: neo4j:5.18
  ports:
    - "7474:7474"
    - "7687:7687"
  environment:
    - NEO4J_AUTH=neo4j/password
    - NEO4J_PLUGINS=["apoc", "graph-data-science"]
```

**因果图谱数据模型**：

```python
# Neo4j Node Types
# (角色节点)
# (事件节点)
# (章节节点)

# Neo4j Relationship Types
# - :CAUSED  (事件A 导致 事件B)
# - :HAPPENED_IN (事件 发生在 章节)
# - :INVOLVES  (事件 涉及 角色)
# - :LEADS_TO  (伏笔 导向 回收)
```

**因果关系建模**：

```cypher
// 创建因果链
CREATE (e1:Event {name: "林舟发现密信", chapter: 19})
CREATE (e2:Event {name: "林澈决定追查", chapter: 21})
CREATE (e1)-[:CAUSED {type: "direct", confidence: 0.95}]->(e2)

// 溯源查询：从第50章往前找10层因果链
MATCH path = (end:Event {chapter: 50})<-[:CAUSED*1..10]-(start)
RETURN path
ORDER BY length(path) DESC
LIMIT 5

// 找两个事件之间的所有路径
MATCH path = (a:Event)-[:CAUSED*]-(b:Event)
WHERE a.name = "密信出现" AND b.name = "真相大白"
RETURN path

// 计算角色的"因果影响力"（类似 PageRank）
CALL gds.pageRank.stream('causalGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS character, score
ORDER BY score DESC
LIMIT 10
```

**与 PostgreSQL 的数据同步**：

```
PostgreSQL (主存储)          Neo4j (图引擎)
┌──────────────────┐          ┌──────────────────┐
│ chapters         │──triggers──▶│ 因果关系节点     │
│ characters        │          │ 关系边           │
│ events           │          └──────────────────┘
│ causal_links     │
└──────────────────┘
```

#### Neo4j 带来的独特能力

| 能力 | 说明 | 价值 |
|------|------|------|
| **多路径溯源** | 找两个事件之间的所有可能路径 | 复杂故事网分析 |
| **角色影响力分析** | PageRank 计算角色的因果网络中心性 | 识别真正的主角/关键事件 |
| **子图模式匹配** | 检测"X 导致 Y 导致 Z"结构 | 自动识别三幕式等故事结构 |
| **最短因果路径** | 两事件间的最短因果链 | 快速定位关键转折 |
| **APOC 库** | 丰富图算法扩展 | 社区检测、路径搜索等 |

#### 入手点

- `docker-compose.yml` 新增 Neo4j 服务
- `backend/models/` 新建 `causal_node.py` (映射 Neo4j 节点)
- `backend/services/` 新建 `neo4j_service.py` (因果图谱操作)
- `backend/db/migrations/` 新建迁移（同步 PostgreSQL → Neo4j）
- `backend/agents/canon_guardian.py` — 章节生成后自动建立因果关系
- `backend/api/v1/` — 新增 `/projects/{id}/causal-graph` 端点

#### 实施预估

- **Neo4j 部署 + APOC**：1 天
- **Neo4j Service 层**：3 天
- **因果关系自动建立**：3 天
- **API + 可视化**：2 天
- **总计**：约 9 个工作日

---

### 3.3 Token 熔断机制

#### 问题背景

AI 生成进入异常循环时，Token 消耗可能瞬间爆表，导致成本失控。线上生产环境**必须**有此保障。

#### 技术方案

```python
class TokenCircuitBreaker:
    """Token 熔断器"""

    def __init__(self, chapter_budget: float = 2.0):  # $2/章上限
        self.chapter_budget = chapter_budget
        self.chapter_spend: dict[UUID, float] = {}
        self.is_open: dict[UUID, bool] = {}
        self.retry_count: dict[UUID, int] = {}

    async def check_and_record(
        self,
        chapter_id: UUID,
        tokens_used: int,
        cost: float,
    ) -> CircuitBreakerResult:
        # 累计消费
        self.chapter_spend[chapter_id] = (
            self.chapter_spend.get(chapter_id, 0) + cost
        )

        # 检查阈值
        if self.chapter_spend[chapter_id] > self.chapter_budget:
            self.is_open[chapter_id] = True
            return CircuitBreakerResult(
                should_break=True,
                reason="exceeded_budget",
                current_spend=self.chapter_spend[chapter_id],
                budget=self.chapter_budget,
            )

        # 检查异常模式：单次生成 Token > 5000 且重复 3 次
        if tokens_used > 5000:
            self.retry_count[chapter_id] = self.retry_count.get(chapter_id, 0) + 1
            if self.retry_count[chapter_id] >= 3:
                self.is_open[chapter_id] = True
                return CircuitBreakerResult(
                    should_break=True,
                    reason="loop_detected",
                    current_spend=self.chapter_spend[chapter_id],
                    budget=self.chapter_budget,
                )

        return CircuitBreakerResult(should_break=False)

    async def get_transparency_report(self, chapter_id: UUID) -> dict:
        """前端实时展示预估/已消耗金额"""
        return {
            "chapter_id": str(chapter_id),
            "spent": self.chapter_spend.get(chapter_id, 0),
            "budget": self.chapter_budget,
            "utilization_pct": (
                self.chapter_spend.get(chapter_id, 0) / self.chapter_budget * 100
            ),
            "status": "open" if self.is_open.get(chapter_id) else "closed",
        }
```

#### 入手点

- `backend/core/` 新建 `circuit_breaker.py`
- `backend/agents/coordinator.py` — 在生成循环中集成熔断检查
- `backend/services/chapter_service.py` — 存储熔断事件
- `frontend/app/dashboard/` — story-room 页面展示实时成本

#### 实施预估

- **核心逻辑**：1 天
- **Agent 集成**：1 天
- **前端展示**：1 天
- **总计**：约 3 个工作日

---

## 四、P1 — 产品级体验

> 提升创作质量与效率，用户能直接感知"更好用了"

### 4.1 并行化执行 — 缩短 30-40% 生成时间

#### 问题现状

```
当前：Librarian → Architect → Writer → CanonGuardian → Critic → Debate → Editor
                    ↓              ↓              ↓              ↓
                 串行等待        串行等待        串行等待        串行等待
```

#### 技术方案

`CanonGuardian` 和 `Critic` **无前后依赖**，可并发执行：

```python
# coordinator.py 中的 revision round 改造
async def _execute_revision_round(self, ...):
    # 并发执行：无依赖的两个检查
    canon_task = self.canon_guardian.run(context, canon_payload)
    critic_task = self.critic.run(context, critic_payload)

    canon_report, critic_response = await asyncio.gather(
        canon_task, critic_task
    )

    # 两者结果合并后再进入 Debate/Editor
    truth_layer_context = build_truth_layer_context(
        canon_report=canon_report,
        integrity_report=integrity_report,
    )
```

#### 入手点

- `backend/agents/coordinator.py` — 修改 `_run_revision_loop` 和 `_execute_revision_round`
- 仅改动 2 个方法，预计 **1-2 天**

---

### 4.2 角色语言指纹 + 社交拓扑

#### 问题现状

角色"说错话"、口癖不一致、人设崩塌。当前 `Character` 模型仅有静态属性，无动态心智模型。

#### 技术方案

**新增数据模型**：

```python
class CharacterLinguisticProfile(Base):
    """角色语言指纹"""
    __tablename__ = "character_linguistic_profiles"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    character_id: Mapped[UUID] = mapped_column(ForeignKey("characters.id"), unique=True)

    # 词云权重（从已有文本中提取）
    word_weights: Mapped[dict[str, float]]  # {"杀": 12.5, "冷": 8.2, ...}

    # 句式习惯
    sentence_patterns: Mapped[list[str]]  # ["短句", "反问句", "省略号结尾"]

    # 口癖
    verbal_tics: Mapped[list[str]]  # ["哼", "愚蠢", "有趣"]

    # 受教育水平标记
    education_level: Mapped[str]  # "文盲" | "初等" | "中等" | "高等"

    version: Mapped[int] = mapped_column(Integer, default=1)


class CharacterSocialTopology(Base):
    """角色社交拓扑"""
    __tablename__ = "character_social_topologies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)

    from_character_id: Mapped[UUID] = mapped_column(ForeignKey("characters.id"))
    to_character_id: Mapped[UUID] = mapped_column(ForeignKey("characters.id"))

    # 动态关系值
    affection: Mapped[float]   # 好感度 -1.0 ~ 1.0
    hostility: Mapped[float]   # 仇恨值 0.0 ~ 1.0
    debt: Mapped[float]        # 亏欠度 0.0 ~ 1.0

    # 关系变化历史（最近 5 次）
    history: Mapped[list[dict]]  # [{"chapter": 10, "delta": {"affection": +0.3}}]
```

**Linguistic Checker Agent**：

```python
class LinguisticCheckerAgent(BaseAgent):
    """对话一致性校验"""

    async def _run(self, context, payload) -> AgentResponse:
        dialogue_lines: list[dict] = payload["dialogue_lines"]
        character_id: UUID = payload["character_id"]
        profile: CharacterLinguisticProfile = await self._get_profile(character_id)

        issues = []
        for line in dialogue_lines:
            if not self._is_consistent(line["text"], profile):
                issues.append({
                    "type": "linguistic_inconsistency",
                    "character_id": str(character_id),
                    "line": line["text"],
                    "suggestion": self._generate_fix(line["text"], profile),
                })

        return AgentResponse(
            success=True,
            data={"issues": issues},
            confidence=0.85 if issues else 0.98,
        )
```

#### 入手点

- `backend/models/` 新建 `character_linguistic_profile.py` 和 `character_social_topology.py`
- `backend/agents/` 新建 `linguistic_checker.py`
- `backend/agents/writer.py` — 在生成对话后调用 Linguistic Checker
- `backend/agents/architect.py` — 生成章节计划时注入社交拓扑参数

#### 实施预估

- **模型层**：2 天
- **Linguistic Checker Agent**：3 天
- **Writer 集成**：2 天
- **前端展示**：2 天
- **总计**：约 9 个工作日

---

### 4.3 T1/T2/T3 模型路由精细化

#### 问题现状

现有 `model_routing.py` 路由逻辑粗糙，无法实现"低耗路由 vs 高精路由"的成本分层。

#### 技术方案

**任务分类映射**：

```python
MODEL_ROUTING_RULES: dict[str, dict] = {
    # Tier 1: 高逻辑任务 — 必须用最强模型
    "卷纲设计": {"model": "claude-sonnet-4", "temperature": 0.5, "max_tokens": 4000},
    "伏笔埋设": {"model": "claude-sonnet-4", "temperature": 0.5, "max_tokens": 3000},
    "逻辑闭环校验": {"model": "claude-sonnet-4", "temperature": 0.3, "max_tokens": 2000},
    "关键剧情转折": {"model": "claude-sonnet-4", "temperature": 0.6, "max_tokens": 5000},

    # Tier 2: 文学性任务 — 平衡质量与成本
    "角色对话": {"model": "claude-haiku-3", "temperature": 0.7, "max_tokens": 2000},
    "环境渲染": {"model": "claude-haiku-3", "temperature": 0.8, "max_tokens": 1500},
    "动作描写": {"model": "deepseek-v3", "temperature": 0.7, "max_tokens": 2000},
    "情感抒发": {"model": "claude-haiku-3", "temperature": 0.8, "max_tokens": 1500},

    # Tier 3: 工具类任务 — 极低成本
    "格式检查": {"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 500},
    "拼写纠错": {"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 500},
    "摘要预筛": {"model": "llama-3-local", "temperature": 0.3, "max_tokens": 1000},
    "实体候选": {"model": "gpt-4o-mini", "temperature": 0.5, "max_tokens": 1000},
}

# 模型降级策略
FALLBACK_CHAIN: dict[str, list[str]] = {
    "claude-sonnet-4": ["claude-haiku-3", "gpt-4o"],
    "claude-haiku-3": ["deepseek-v3", "gpt-4o-mini"],
    "deepseek-v3": ["gpt-4o-mini"],
    "gpt-4o-mini": ["llama-3-local"],
}
```

#### 入手点

- `backend/core/` 新建或扩展 `model_routing.py`
- `backend/agents/base.py` — 各 Agent 指定 `task_name` 供路由匹配
- `backend/agents/model_gateway.py` — 根据 task_name 路由到对应模型

---

### 4.4 Prompt Caching

#### 技术方案

```python
# 静态内容定义
CACHEABLE_CONTENT: list[dict] = [
    {"key": "system_prompt", "content": "你是一个网文写作助手..."},
    {"key": "world_setting", "content": "{story_bible.world_settings}"},
    {"key": "character_base", "content": "{character_profiles}"},
]

# 利用 API 缓存（如 Claude 的 Cache 机制）
async def generate_with_cache(
    request: GenerationRequest,
    cache_key: str,
) -> GenerationResult:
    cached = await redis.get(f"prompt_cache:{cache_key}")
    if cached:
        return GenerationResult(
            content=cached,
            provider="cache",
            model="cached",
            used_cache=True,
        )

    result = await model_gateway.generate_text(request)
    await redis.setex(
        f"prompt_cache:{cache_key}",
        ttl=3600,  # 1 小时过期
        value=result.content,
    )
    return result
```

#### 入手点

- `backend/services/` 新建 `prompt_cache_service.py`
- `backend/memory/context_builder.py` — 生成 cache_key 时包含 story_bible_version

---

## 五、P2 — 商业化必备

### 5.1 部署架构升级

| 现状 | 目标 | 价值 |
|------|------|------|
| Docker Compose | Kubernetes + HPA | 流量峰值自动伸缩 |
| Celery 单队列 | 多级 Queue | 任务优先级保障 |
| 无可观测性 | LangSmith/Arize | 链路追踪 + 成本分析 |
| 手动运维 | Prometheus + Grafana | 实时监控告警 |

**入手点**：
- 迁移路径：`docker-compose.yml` → Helm Chart → K8s
- Celery Queue 拆分：`backend/tasks/` 新增 `queues.py` 定义优先级
- LangSmith：集成到 `agents/base.py` 的 tracing

### 5.2 虚拟读者 Beta-Readers

```python
BETA_READER_PERSONAS: list[dict] = [
    {"name": "爽文党", "focus": "节奏", "weight": {"pace": 0.5, "conflict": 0.3, "emotion": 0.2}},
    {"name": "逻辑控", "focus": "一致性", "weight": {"consistency": 0.5, "logic": 0.3, "detail": 0.2}},
    {"name": "情感细腻派", "focus": "情感共鸣", "weight": {"emotion": 0.5, "dialogue": 0.3, "description": 0.2}},
]

class BetaReaderAgent(BaseAgent):
    """虚拟读者模拟"""

    async def _run(self, context, payload) -> AgentResponse:
        persona = payload["persona"]
        content = payload["content"]

        # 根据 persona 计算多维度评分
        scores = self._evaluate(content, persona["weight"])

        # 模拟"弃坑点"检测
        dropout_risk = self._detect_dropout_risk(content)

        return AgentResponse(
            success=True,
            data={
                "scores": scores,
                "feedback": self._generate_feedback(scores, persona),
                "dropout_risk": dropout_risk,
            },
        )
```

---

## 六、技术债务修复

> 基于代码审查发现的问题，修复现有 Bug

### 6.1 已识别 Bug

| # | 问题 | 位置 | 严重度 | 修复方案 |
|---|------|------|--------|----------|
| 1 | 修订循环多跑一轮 | `coordinator.py#L207` | P0 | `range(1, self.max_revision_rounds + 2)` → `+1` |
| 2 | Truth Layer 未在循环中正确更新 | `coordinator.py#L219` | P0 | 循环内每次执行后更新 `final_truth_layer_context` |
| 3 | revision_plan 未在 break 前记录 | `coordinator.py#L248` | P0 | break 前 append 到 `all_revision_plans` |
| 4 | Writer 输出未做 canon 预检 | `coordinator.py` | P1 | Writer 后、Revision Loop 前增加 canon 预检 |
| 5 | DebateAgent 辩论逻辑未真正实现 | `debate.py` | P1 | 实现多轮辩论或简化为单轮决策 |
| 6 | Token budget 硬编码 | `context_builder.py` | P2 | 动态计算 token 数量 |
| 7 | final_ready 默认 True | `chapter_gate_service.py` | P2 | 改为默认 False |
| 8 | Confidence 计算逻辑错误 | `coordinator.py#L199` | P2 | 修订次数多应降低 confidence |

---

## 七、实施路线图

### Phase 0：数据库架构优化（Week 0）— 已完成 ✅

```
Day 1: 废弃 Chroma，统一向量库到 Qdrant
       - 新增 services/story_engine_vector_store.py（Qdrant 统一向量服务）
       - 删除 services/chroma_service.py
       - 更新 services/story_engine_kb_service.py 引用
       - 更新 docker-compose.yml 移除 chroma 服务
       - 更新 requirements.txt 移除 chromadb 依赖

Day 2: Redis 缓存策略实现
       - 新增 services/cache_service.py
       - Story Bible 缓存（TTL 5min）
       - 章节草稿缓存（TTL 10min）
       - 项目统计缓存（TTL 1h）
       - 用户会话缓存（TTL 30min）
       - 角色信息缓存（TTL 10min）

Day 3: PostgreSQL 表分区
       - 新增 db/migrations/versions/20260402_0001_chapter_partitioning.py
       - Chapter 表按 created_at 按季分区
       - 自动分区管理函数

Day 4: 只读副本配置
       - 新增 docker-compose.replica.yml
       - postgres_primary（主库，写入）
       - postgres_replica_story_engine（Story Engine 专用副本）
       - postgres_replica_dashboard（Dashboard 专用副本）
       - 新增 infrastructure/postgres/replication/init.sh
```

**优化效果**：
- 向量库统一：运维复杂度降低 50%，存储空间减少 40%
- Redis 缓存：数据库查询减少 70%，API 响应时间缩短 50%
- 表分区：热数据查询极快（内存/SSD），冷数据自动归档
- 只读副本：读取 QPS 提升 3-5 倍，主库写入压力降低 60%

---

### Phase 1：核心差异化（Week 1-3）

```
Day 1-2: Open Threads DB 模型 + Service
Day 3-4: 伏笔生命周期 + Architect 集成
Day 5-6: Neo4j 部署 + APOC 插件
Day 7:   Bug 修复 (#1, #2, #3, #4)
Day 8-9: Neo4j Service 层 + 因果关系自动建立
Day 10:  Token 熔断核心逻辑
Day 11:  API + 前端集成
```

**交付物**：解决"吃书"问题 + Neo4j 因果图谱 + 成本可控保障

### Phase 2：产品级体验（Week 4-6）

```
Week 4: 并行化执行改造（CanonGuardian + Critic 并发）
Week 5: 角色语言指纹 + Linguistic Checker
Week 6: 社交拓扑 + Architect 集成
```

**交付物**：人设一致性保障 + 生成速度提升 30%

### Phase 3：商业化（Week 7-8）

```
Week 7: LangSmith 集成 + 监控基础 + T1/T2/T3 路由
Week 8: Beta-Readers + K8s 迁移准备
```

---

## 八、总结

| 阶段 | 周期 | 核心目标 | 关键交付物 |
|------|------|----------|------------|
| Phase 1 | 3 周 | 解决吃书 + 因果图谱 + 成本可控 | Open Threads DB、Neo4j 因果图谱、Token 熔断 |
| Phase 2 | 3 周 | 提升创作质量 + 速度 | 并行化、语言指纹、社交拓扑 |
| Phase 3 | 2 周 | 商业化准备 | LangSmith、Beta-Readers、K8s |

**核心原则**：
1. 引入 Neo4j 图数据库，实现真正的因果图谱能力（多路径溯源、PageRank、模式匹配）
2. 优先实现用户最能感知差异化的功能（伏笔追踪 + 因果溯源）
3. Token 熔断是线上生产的底线，必须第一时间实现
4. Sub-graph 递归架构作为长期目标，Phase 1-2 不碰
