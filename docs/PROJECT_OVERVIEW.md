# Novel Agent — 项目概览

## 项目简介

Novel Agent 是一个**多智能体协作的长篇小说创作引擎**，通过多个专业 AI Agent 的分工协作，完成从世界观构建、大纲规划到章节正文生成、全文审校的全流程。

> 核心技术栈：FastAPI + Celery（后端）、Next.js 14 + React 18（前端）、PostgreSQL + Qdrant + Neo4j + Redis（数据层）。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                    │
│   Dashboard │ World-Building │ Style Analysis │ Prompt 管理  │
└──────────────────────────────┬────────────────────────────────┘
                               │ HTTP / WS
┌──────────────────────────────▼────────────────────────────────┐
│                     Backend (FastAPI + Celery)                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Task Dispatch (Celery Queues)           │     │
│  │  critical │ high │ normal │ low                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────┐  │
│  │  Agent   │  Memory  │   Core   │ Services │Infrastructure│  │
│  │  Layer   │  Layer   │  Engine  │  Layer   │           │  │
│  │  15 agents│ L1/L2/L3 │ Truth    │ 30+ svcs │ metrics  │  │
│  │          │          │  Layer   │          │ tracing   │  │
│  │          │          │          │          │ circuit  │  │
│  │          │          │          │          │ breaker   │  │
│  └──────────┴──────────┴──────────┴──────────┴───────────┘  │
└──────────────────────────────┬────────────────────────────────┘
                               │
     ┌──────────────┬──────────┼──────────┬──────────────┐
     ▼              ▼          ▼          ▼              ▼
  PostgreSQL     Qdrant      Neo4j      Redis         S3/CDN
  (主数据)      (向量检索)   (因果图谱)  (缓存/队列)   (文件存储)
```

---

## Agent Layer（15 个智能体）

| Agent | 类名 | 核心职责 |
|-------|------|---------|
| **Coordinator** | `CoordinatorAgent` | 全流程编排，revision loop 控制，真相层上下文传递 |
| **Architect** | `ArchitectAgent` | 根据 Story Bible 生成章节计划和大纲 |
| **Writer** | `WriterAgent` | 分 4 段生成正文（开篇/发展/高潮/收尾），支持断点续传 |
| **Critic** | `CriticAgent` | 多维度质量评审，驱动 revision loop |
| **CanonGuardian** | `CanonGuardianAgent` | 保护 Story Bible 一致性，拦截典律冲突 |
| **Editor** | `EditorAgent` | 基于评审意见执行 prose 改进 |
| **Debate** | `DebateAgent` | 探索叙事冲突和张力，生成修订计划 |
| **Approver** | `ApproverAgent` | 最终审批决策 |
| **Librarian** | `LibrarianAgent` | 知识检索，构建受 token 预算约束的上下文 |
| **LinguisticChecker** | `LinguisticCheckerAgent` | 语言指纹校验，确保角色说话方式一致 |
| **BetaReader** | `BetaReaderAgent` | 虚拟读者，动态 Persona 权重，注入 revision loop |
| **ChaosAgent** | `ChaosAgent` | 混沌干预，引入叙事 twists |
| **ModelGateway** | — | T1/T2/T3 分级路由 + FALLBACK_CHAIN 降级链 |

### Agent 基座能力

所有 Agent 继承 `BaseAgent`，具备：
- **指数退避重试**：最多 3 次，间隔 1s/2s/4s
- **Fallback 降级**：主模型失败自动切换降级链
- **LangSmith 链路追踪**：每次调用可追踪

---

## Memory Layer（三层记忆系统）

| 层级 | 类型 | 存储内容 | Token 预算 |
|------|------|---------|-----------|
| **L1 Working** | Working Memory | 当前任务上下文 | ~40% |
| **L2 Episodic** | Episodic Memory | 最近 5 章摘要 + 关键事件 | ~15% |
| **L3 Long-term** | Long-term Memory | 世界规则、角色弧线、叙事弧压缩 | ~20% |

### 关键组件

- **`context_builder.py`**：基于 token 预算的检索上下文构建，支持 Vector Store 召回
- **`vector_store.py`**：Qdrant 向量检索，按类型（character/plot_thread/foreshadowing 等）分批查询
- **`story_bible.py`**：World Bible 上下文封装，包含 characters/locations/foreshadowing 等

---

## Core Engine（真相层引擎）

### Truth Layer

`build_truth_layer_context()` 合并两类报告：
- **Integrity Report**：Story Bible 内部一致性校验（Canon 模块）
- **Canon Report**：章节内容对 Story Bible 的遵循度

每次 revision loop 轮次结束后更新 `final_truth_layer_context`，确保后续处理使用最新上下文。

### Temporal Logic Engine

`core/temporal_logic_engine.py` — 时间线一致性验证：
- 检测 flashback / flashforward
- Duration Claim 验证
- 时间线冲突预警

### Token Circuit Breaker

`core/circuit_breaker.py` — 成本控制：
- 按 chapter 设置 token 预算上限（$2/章）
- loop 检测（连续 3 次相同 content hash）
- 超出预算时熔断

### 其他 Core 组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **LangSmith Tracing** | `core/langsmith_tracing.py` | 全链路追踪 |
| **Prometheus Metrics** | `core/metrics.py` | 可观测性指标 |
| **Rate Limiting** | `core/rate_limit.py` | 限流 |

---

## Services Layer（核心服务）

### 生成与流程

| 服务 | 文件 | 功能 |
|------|------|------|
| **GenerationService** | `services/generation_service.py` | 主编排管道，断点检测，Neo4j 读写，social_topology 注入 |
| **StoryEngineWorkflowService** | `services/story_engine_workflow_service.py` | 大型工作流（outline stress test / realtime guard / bulk import） |
| **EntityGenerationService** | `services/entity_generation_service.py` | 角色/物品/地点/派系/情节线批量生成 |

### 记忆与上下文

| 服务 | 文件 | 功能 |
|------|------|------|
| **CheckpointService** | `services/checkpoint_service.py` | Writer 断点续传，保存/恢复生成快照 |
| **L2EpisodicMemory** | `memory/l2_episodic.py` | 章节剧情摘要持久化 |
| **SemanticCompressionService** | `services/semantic_compression_service.py` | 20+ 章时按叙事弧压缩，降低 importance_score |
| **PromptCacheService** | `services/prompt_cache_service.py` | LLM prompt 结果缓存 |
| **ContextBuilder** | `memory/context_builder.py` | 构建受 token 预算约束的检索上下文 |

### 质量保障

| 服务 | 文件 | 功能 |
|------|------|------|
| **ForeshadowingLifecycleService** | `services/foreshadowing_lifecycle_service.py` | 伏笔生命周期（open→tracking→resolution_pending→resolved→abandoned） |
| **TensionSensorService** | `services/tension_sensor_service.py` | 叙事张力评分和等级 |
| **SocialTopologyService** | `services/social_topology_service.py` | 角色关系拓扑图谱，中心性得分计算 |
| **UndoRedoService** | `services/undo_redo_service.py` | 章节快照版本管理 |
| **EvaluationService** | `services/evaluation_service.py` | 章节质量评估报告 |

### 数据库与基础设施

| 服务 | 文件 | 功能 |
|------|------|------|
| **Neo4jService** | `services/neo4j_service.py` | 因果图谱创建/查询/角色影响力计算 |
| **CacheService** | `services/cache_service.py` | Redis 通用缓存 |
| **ChapterGateService** | `services/chapter_gate_service.py` | 章节发布门禁检查 |
| **TruthLayerService** | `services/truth_layer_service.py` | 真相层报告生成 |

---

## 数据模型（关键表）

### 核心业务表

| 模型 | 文件 | 用途 |
|------|------|------|
| `Project` | `models/project.py` | 项目 |
| `Chapter` | `models/chapter.py` | 章节 |
| `ChapterVersion` | `models/chapter_version.py` | 章节历史版本 |
| `ChapterCheckpoint` | `models/chapter_checkpoint.py` | 生成断点快照 |
| `ChapterSnapshot` | `models/chapter_snapshot.py` | 手动快照 |
| `Character` | `models/character.py` | 角色 |
| `Location` | `models/location.py` | 地点 |
| `Foreshadowing` | `models/foreshadowing.py` | 伏笔 |
| `PlotThread` | `models/plot_thread.py` | 情节线 |
| `OpenThread` | `models/open_thread.py` | 伏笔生命周期追踪 |
| `ProjectBranch` | `models/project_branch.py` | 故事分支 |

### 记忆与质量表

| 模型 | 文件 | 用途 |
|------|------|------|
| `ChapterEpisode` | `memory/l2_episodic.py` | L2 剧情摘要 |
| `TensionSensor` | `models/tension_sensor.py` | 张力评分记录 |
| `CharacterSocialTopology` | `models/social_topology.py` | 角色关系图谱 |
| `CharacterLinguistic` | `models/character_linguistic.py` | 语言指纹 |
| `TimelineEvent` | `models/timeline_event.py` | 时间线事件 |

### 协作与评估表

| 模型 | 文件 | 用途 |
|------|------|------|
| `Evaluation` | `models/evaluation.py` | 质量评估记录 |
| `ChapterReviewDecision` | `models/chapter_review_decision.py` | 审阅决策 |
| `PromptTemplate` | `models/prompt_template.py` | Prompt 模板 |
| `UserPreference` | `models/user_preference.py` | 用户偏好 |

---

## 任务队列（Celery）

四级优先级队列：

```
celery -Q critical,high,normal,low

# 路由规则
chapter_generation  → critical
entity_generation   → high
world_building     → normal
export / cleanup   → low
```

任务状态通过 `Redis` + `TaskStateStore` 持久化，支持 WebSocket 实时推送。

---

## 前端（Next.js 14）

### 核心页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 项目仪表盘 | `/dashboard/projects/[projectId]` | 项目总览 |
| 世界构建 | `/dashboard/projects/[projectId]/world-building/` | 角色/地点/派系/物品编辑 |
| 章节管理 | `/dashboard/projects/[projectId]/chapters/` | 章节列表与生成 |
| 风格分析 | `/dashboard/style-analysis/` | 用户风格画像 |
| Prompt 模板 | `/dashboard/prompt-templates/` | Prompt 模板管理 |

### 关键组件

| 组件 | 用途 |
|------|------|
| `BetaReaderPanel` | 虚拟读者反馈展示 |
| `TensionDisplay` | 张力曲线可视化 |
| `ChapterHistoryPanel` | 章节历史版本对比 |
| `DeliveryCenterPanel` | 一键分发管理 |
| `SmartRecommendPanel` | 智能推荐面板 |

### 核心 Hooks

| Hook | 用途 |
|------|------|
| `useUndoRedo` | 撤销/重做 |
| `useTaskEventStream` | WebSocket 任务事件流 |

---

## 基础设施（Infrastructure）

### Kubernetes

- `backend-deployment.yaml`：2 replicas，metrics 端口 9090，Prometheus scrape annotations
- `backend-hpa.yaml`：HPA 自动扩缩容
- `celery-hpa.yaml`：Celery worker 自动扩缩
- 环境变量全量配置：NEO4J / QDRANT / REDIS / LANGCHAIN / OPENAI 等

### 数据库

- **PostgreSQL**：主数据，分区表（chapter_partitioning）
- **Qdrant**：向量检索（Story Bible / characters / foreshadowing）
- **Neo4j**：因果图谱，角色关系图
- **Redis**：缓存 + Celery broker + Rate limiting

---

## 已实现的核心能力

- ✅ **多 Agent 协作**：15 个专业 Agent 完整协作流程
- ✅ **三层记忆系统**：L1/L2/L3 完整实现
- ✅ **Writer 断点续传**：4 段生成 + CheckpointService，支持中断恢复
- ✅ **BetaReader 动态 Persona**：根据 tension/历史/章节号自适应权重
- ✅ **Neo4j 因果图谱闭环**：生成前查询因果路径 + 生成后写入事件节点
- ✅ **social_topology 注入**：角色关系图谱传入所有相关 Agent
- ✅ **Model FALLBACK_CHAIN**：claude-sonnet-4 → claude-haiku-3 → gpt-4o 降级链
- ✅ **Token Circuit Breaker**：$2/章预算，loop 检测
- ✅ **Temporal Logic Engine**：时间线一致性验证
- ✅ **Foreshadowing 生命周期**：open→resolution 全链路追踪
- ✅ **Semantic Compression**：长篇叙事弧压缩
- ✅ **多级 Celery 队列**：critical/high/normal/low 四级优先级
- ✅ **Prometheus 可观测性**：metrics 端口 9090
- ✅ **38 个单元测试**：pytest 全部通过

---

## 项目结构

```
novel-agent/
├── backend/
│   ├── agents/              # 15 个 Agent
│   ├── api/                 # FastAPI 路由
│   ├── bus/                 # 消息总线协议
│   ├── canon/               # Canon 典律校验模块
│   ├── core/                # 真相层/熔断器/可观测性
│   ├── db/                  # SQLAlchemy session / migrations
│   ├── memory/              # L1/L2/L3 记忆系统
│   ├── models/              # 30+ 数据模型
│   ├── schemas/             # Pydantic 请求/响应模型
│   ├── scripts/             # 工具脚本
│   ├── services/           # 30+ 业务服务
│   ├── tasks/               # Celery 任务定义
│   └── tests/               # 单元测试
├── frontend/
│   ├── app/                 # Next.js 14 App Router
│   ├── components/          # React 组件
│   ├── hooks/               # 自定义 Hooks
│   ├── lib/                 # 工具函数
│   └── tests/               # 前端测试
├── infrastructure/
│   └── k8s/                 # Kubernetes 部署配置
├── docs/                    # 项目文档
└── PRD.md / WRITING_FLOW_REDESIGN.md  # 需求文档
```

---

## 技术栈速查

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Pydantic v2 |
| 异步任务 | Celery 5.x + Redis |
| ORM | SQLAlchemy 2.x (async) |
| Python | 3.9+ |
| 前端框架 | Next.js 14 (App Router) |
| 前端语言 | TypeScript 5 |
| 向量数据库 | Qdrant |
| 图数据库 | Neo4j |
| 缓存 | Redis |
| 链路追踪 | LangSmith |
| 可观测性 | Prometheus |
| 部署 | Kubernetes (K8s) |
