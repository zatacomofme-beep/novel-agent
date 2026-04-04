# Novel Agent 项目概览

## 说明

这份文档描述的是当前仓库代码的真实现状，不是历史全景设计，也不是未来规划。

本文档的目标只有三个：

1. 说明当前产品主线是什么
2. 说明哪些能力仍在主链上，哪些已经退到底层或遗留层
3. 为后续改造提供稳定的判断基线，避免误删核心能力

---

## 项目定位

Novel Agent 当前的真实定位是：

**一个以 `story-room` 为主入口、以 Story Engine 工作流为主编排、以正式章节链和动态知识链双真相层为基础的长篇小说创作系统。**

它不是单纯的文本生成器，也不是面向作者暴露内部代理细节的调度台。

当前产品意图可以概括为：

- 让作者只在一个主工作台里完成开书、大纲、起稿、审校、终稿和知识沉淀
- 让系统维护长篇创作中的事实源，而不是依赖模型“记住”
- 让生成、审校、知识更新、任务状态都可追踪、可恢复、可回放

---

## 当前主线

当前代码已经形成了一条比较清晰的主线：

### 1. 前端主入口

当前真正面向作者的主入口是：

- `/dashboard`
- `/dashboard/projects/[projectId]/story-room`

大量历史项目页面已经重定向回 `story-room`，例如：

- `chapters`
- `bible`
- `quality`
- `settings`
- `bootstrap`
- `generations/*`

这说明产品入口已经收口，`story-room` 是当前唯一主工作台。

### 2. 后端主入口

当前主后端入口是：

- `backend/api/v1/story_engine.py`
- `backend/services/story_engine_workflow_service.py`
- `backend/services/story_engine_kb_service.py`

这条主线负责：

- 工作区装载
- 知识库读写
- 模型路由读取与更新
- 大纲压力测试
- 实时护栏
- 流式章节起稿
- 终稿优化
- 云草稿
- 统一工作流时间线

### 3. 正式章节主链

作者在 `story-room` 中生成和保存的正式章节，仍然落到正式章节链：

- `Chapter`
- `ChapterVersion`
- `Review`
- `Checkpoint`
- `Evaluation`
- `Final Gate`

这条链是“正式章节真相层”，负责：

- 章节版本
- 审校状态
- 质量评估
- 发布门禁

### 4. 动态知识主链

Story Engine 维护另一条“动态事实层”，主要包括：

- 人物
- 伏笔
- 物品
- 世界规则
- 时间线事件
- 大纲
- 章节总结
- 设定版本记录

这条链负责支撑后续生成、设定校验、搜索与知识回写。

---

## 两个真相层

当前代码里最重要的结构，不是“有多少代理”，而是这两个真相层：

### 正式章节真相层

以 `Chapter` 为中心，解决“这一章现在是否可发布”的问题。

核心对象：

- `Chapter`
- `ChapterVersion`
- `ChapterReviewDecision`
- `ChapterCheckpoint`
- `Evaluation`
- `ChapterGateSummary`

这是正式内容链。

### 动态知识真相层

以 Story Engine 结构化实体为中心，解决“当前项目里什么设定算真”的问题。

核心对象：

- `StoryCharacter`
- `StoryForeshadow`
- `StoryItem`
- `StoryWorldRule`
- `StoryTimelineMapEvent`
- `StoryOutline`
- `StoryChapterSummary`
- `StoryKnowledgeVersion`

这是动态知识链。

---

## 当前工作流

当前主工作流围绕 `story-room` 展开，可分为四段：

### 1. 开书与大纲

核心工作流：

- 批量导入设定
- 起盘模板导入
- `outline-stress-test`

目标：

- 生成三级大纲
- 生成初始知识库
- 做设定、逻辑、节奏层面的挑刺与收敛

### 2. 正文起稿

核心工作流：

- `chapter-stream`

目标：

- 按细纲流式起稿
- 允许中途暂停、继续、修补
- 保留工作流时间线

### 3. 写中护栏

核心工作流：

- `realtime-guard`

目标：

- 在正文生成过程中检查设定冲突、逻辑问题和节奏风险
- 必要时暂停并给出修补建议

### 4. 终稿收束

核心工作流：

- `final-optimize`

目标：

- 汇总多角色审视结果
- 给出终稿优化稿
- 生成章节总结
- 给出知识更新建议

---

## 当前系统分层

### 前端层

当前真正处于主产品链上的前端页面：

- `dashboard`
- `story-room`
- `preferences`
- `admin/model-routing`
- `collaborators`

代码存在但不属于当前主入口主链的页面：

- `style-analysis`
- `prompt-templates`
- `world-building`

注意：这些页面文件存在，不代表它们已经纳入当前正式产品主链。

### API 层

当前已接入统一 API 路由的核心模块：

- `auth`
- `dashboard`
- `profile`
- `projects`
- `chapters`
- `evaluation`
- `tasks`
- `story-engine`
- 若干领域辅助模块

代码存在但未接入统一主路由的旁系 API：

- `style_analysis.py`
- `prompt_templates.py`

这类模块不能直接视为当前正式 API 面。

### 工作流层

当前主工作流层是：

- `story_engine_workflow_service.py`

它是当前主产品的真实编排中枢。

### 任务层

当前任务系统是统一的，旧链和新链都复用：

- `TaskRun`
- `TaskEvent`
- `TaskState`
- `task_state_store`
- `task_event_broker`

因此，“任务系统”是共享底座，不属于遗留链。

### 存储层

当前仓库明确在用：

- PostgreSQL
- Redis
- Qdrant
- Neo4j

这些都在 `docker-compose.yml` 中直接起服务。

---

## 当前模块角色划分

下表用于指导后续改造。

| 模块 | 当前角色 | 主线程度 | 修改约束 |
| --- | --- | --- | --- |
| `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` | 当前唯一主工作台 | 主线 | 重点保护，避免新增平行主入口 |
| `backend/api/v1/story_engine.py` | 当前主后端产品入口 | 主线 | 后续新功能优先接入这里 |
| `backend/services/story_engine_workflow_service.py` | 当前主工作流编排层 | 主线 | 可扩展，不应被旧生成链反向牵制 |
| `backend/services/story_engine_kb_service.py` | 当前动态知识层核心服务 | 主线 | 设定搜索、版本记录、工作区装载要保持稳定 |
| `backend/models/story_engine.py` | 当前动态知识模型主表 | 主线 | 不可破坏实体和版本语义 |
| `backend/models/chapter.py` 及相关章节模型 | 当前正式章节真相层 | 主线 | 不可破坏版本、审校、发布门禁 |
| `backend/services/review_service.py` | 当前正式审校底座 | 主线底座 | 可被 `story-room` 继续复用 |
| `backend/services/chapter_service.py` | 当前章节生命周期底座 | 主线底座 | 不可破坏正式章节链 |
| `backend/services/task_service.py` | 当前统一任务持久化底座 | 主线底座 | 新旧任务共享，必须稳定 |
| `backend/realtime/task_events.py` | 当前统一任务实时推送底座 | 主线底座 | 不可破坏订阅与回放能力 |
| `backend/tasks/story_engine_workflows.py` | 当前 Story Engine 异步工作流入口 | 主线 | 后续长任务优先走这条链 |
| `backend/tasks/chapter_generation.py` | 旧章节生成任务入口 | 遗留主链 | 暂时保留，后续迁移后可降级或移除 |
| `backend/services/generation_service.py` | 旧多代理章节生成编排 | 遗留主链 | 不再承载新产品能力 |
| `backend/agents/coordinator.py` 及旧 concrete agents | 旧生成体系核心实现 | 遗留主链 | 仅在确认能力已迁移后再清理 |
| `frontend/app/dashboard/editor/[chapterId]/page.tsx` | 已退场页面 | 遗留 UI | 可视为历史入口 |
| `frontend/app/dashboard/projects/[projectId]/chapters/page.tsx` | 已重定向页面 | 兼容入口 | 不再作为独立产品面扩展 |
| `frontend/app/dashboard/style-analysis/page.tsx` | 旁系页面 | 旁系能力 | 先确认是否纳入正式产品再决定接线 |
| `frontend/app/dashboard/prompt-templates/page.tsx` | 旁系页面 | 旁系能力 | 同上 |
| `frontend/app/dashboard/projects/[projectId]/world-building/page.tsx` | 旁系页面 | 旁系能力 | 同上 |
| `backend/api/v1/style_analysis.py` | 代码存在但未接入主路由 | 旁系能力 | 不能假定已在线可用 |
| `backend/api/v1/prompt_templates.py` | 代码存在但未接入主路由 | 旁系能力 | 同上 |

---

## 当前代理体系的真实情况

当前仓库里存在两套“代理语义”：

### 1. 旧 concrete agents

例如：

- `CoordinatorAgent`
- `ArchitectAgent`
- `WriterAgent`
- `CriticAgent`
- `CanonGuardianAgent`
- `EditorAgent`
- `DebateAgent`
- `ApproverAgent`
- `LibrarianAgent`
- `LinguisticCheckerAgent`
- `BetaReaderAgent`
- `ChaosAgent`

这些主要仍服务于旧章节生成链。

### 2. 新 Story Engine 角色层

当前 Story Engine 更依赖角色配置，而不是直接以旧 concrete agents 为产品表达：

- outline
- guardian
- logic
- commercial
- style
- anchor
- arbitrator
- stream_writer

这些角色由：

- `story_engine_settings_service.py`
- `story_engine_model_service.py`
- `story_agents.py`

共同支撑。

所以，当前项目不能简单描述为“15 个代理共同组成当前主产品架构”。

更准确的说法是：

**旧 concrete agents 仍存在并服务旧链；当前主产品更多依赖 Story Engine 的角色化工作流。**

---

## 当前基础设施现状

### 已明确落地

- Docker Compose 本地运行
- PostgreSQL
- Redis
- Qdrant
- Neo4j
- FastAPI
- Celery
- Next.js

### 已存在部署资产

仓库中存在 Kubernetes 配置，路径在：

- `infrastructure/k8s/base`

因此可以说“存在 K8s 部署资产”，但文档里必须写准确路径。

### 不应直接写成当前既有事实的内容

以下内容除非确认已接线，否则不应写成当前必备基础设施：

- S3 / CDN 作为正式运行依赖
- 所有旁系页面都已在线可用
- 所有历史服务都已纳入统一 API 面

---

## 当前最重要的架构判断

当前项目最重要的判断不是“还有多少遗留代码”，而是：

1. 产品主线已经收口到 `story-room`
2. 工作流主线已经收口到 Story Engine
3. 正式章节链和动态知识链已经形成双真相层
4. 旧章节生成链仍然存在，但已经不是主产品入口
5. 旁系能力仍有代码资产，但很多未正式接入主产品面

---

## 当前改造原则

后续如果继续收口项目，应默认遵循以下原则：

- 不破坏 `story-room` 作为唯一主工作台
- 不破坏正式章节链
- 不破坏 Story Engine 工作流主线
- 不破坏统一任务系统和过程回放
- 不再给旧 `generation_service` 链新增核心产品能力
- 对旁系能力先判断“保留并接线”还是“明确降级”，再决定是否继续投入

---

## 推荐阅读顺序

如果要理解当前项目现状，推荐按下面顺序读：

1. `README.md`
2. `docs/architecture/README.md`
3. `docs/architecture/chapter-lifecycle.md`
4. `docs/architecture/api-contract-map.md`
5. `backend/api/v1/story_engine.py`
6. `backend/services/story_engine_workflow_service.py`
7. `backend/services/story_engine_kb_service.py`
8. `backend/models/chapter.py`
9. `backend/models/story_engine.py`

---

## 一句话总结

当前 Novel Agent 的真实状态不是“所有历史设计都仍然同等在役”，而是：

**主产品已经围绕 `story-room + Story Engine + 正式章节链` 收口，但旧生成链和若干旁系能力仍作为遗留或未完全接线资产存在。**
