# 长篇小说创作流程重构 - 技术设计文档

> 创建时间：2026-03-27
> 状态：待评审

---

## 一、现状分析

### 1.1 现有项目核心结构

| 模型 | 说明 |
|-----|------|
| `Project` | 项目根实体，包含 `bootstrap_profile`（引导配置）、`novel_blueprint`（大纲）、`story_engine_settings` |
| `Chapter` | 章节，含 `outline`（大纲 JSON）、`content`（正文）、`status`（draft/approved/published） |
| `WorldSetting` | 世界设定（key-value 形式） |
| `Character`, `Location`, `Faction`, `Item` | 各类实体 |
| `PlotThread`, `Foreshadowing`, `TimelineEvent` | 剧情线、伏笔、时间线 |
| `StoryBibleVersion` | 圣经版本记录 |
| `StoryBiblePendingChange` | 待审批的圣经变更 |

### 1.2 现有流程

```
用户想法 → 手动填写 bootstrap_profile → 生成 blueprint（大章纲） → 生成章节 → 审阅
```

### 1.3 现有 Agent 集群

| Agent | 职责 |
|-------|------|
| `CoordinatorAgent` | 协调各 Agent 工作流 |
| `ArchitectAgent` | 生成大纲 |
| `WriterAgent` | 生成正文 |
| `CriticAgent` | 提供批评意见 |
| `DebateAgent` | 辩论挑刺 |
| `EditorAgent` | 编辑修订 |
| `ApproverAgent` | 最终审批 |
| `CanonGuardianAgent` | 设定守护 |

---

## 二、目标流程

### 2.1 三阶段创作模型

```
第一阶段：想法输入 → 引导式世界观生成 → 大纲确认
第二阶段：章节细纲 + 写作意图确认
第三阶段：章节生成 → 审阅循环（通过 / 手动改 / Agent 改）
```

### 2.2 流程详情

#### 第一阶段：引导式世界观生成

| 步骤 | 说明 |
|-----|------|
| 用户输入 | 用户直接输入一句话想法："我想写一个修仙世界，主角从废物流崛起" |
| AI 引导 | Gemini 3.1 Pro 通过 8 步引导，让用户补充世界观、力量体系、社会结构等 |
| 生成大纲 | 基于收集的信息，生成三级章纲（chapter_blueprints） |
| 用户审阅 | 用户确认大纲，或修改不满意的部分 |
| 进入下一阶段 | 大纲确认后进入第二阶段 |

#### 第二阶段：细纲 + 写作意图确认

| 步骤 | 说明 |
|-----|------|
| 选择章节 | 用户选择要写的章节 |
| 查看/修改细纲 | 用户查看该章节的 `objective` 和 `summary`，可修改 |
| AI 阐述写作意图 | **新字段 `writing_intent`**：AI 先输出 100-300 字，说明本章打算怎么写 |
| 用户确认 | 用户确认写作意图，或直接修改意图内容 |
| 开始生成 | 用户确认后，触发 Agent 集群开始写 |

#### 第三阶段：生成 + 审阅循环

| 步骤 | 说明 |
|-----|------|
| Agent 执行 | Agent 集群生成章节初稿 |
| 用户审阅 | 用户审阅生成的章节 |
| 三种分支 | OK → 通过并保存 / 手动改 → 直接编辑保存 / 反馈 → Agent 重新生成 |

---

## 三、详细设计

### 3.1 新增/修改的数据模型

#### 3.1.1 新增：`Chapter` 表增加 `writing_intent` 字段

```python
# models/chapter.py 修改
class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    # ... 现有字段 ...
    writing_intent: Mapped[Optional[str]] = mapped_column(Text)  # 新增
    writing_intent_approved: Mapped[bool] = mapped_column(default=False)  # 新增
```

#### 3.1.2 新增：引导式世界观生成会话表

```python
# models/world_building_session.py（新建）
class WorldBuildingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "world_building_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    current_step: Mapped[int] = mapped_column(default=1)  # 1-8 对应引导步骤
    session_data: Mapped[dict] = mapped_column(JSONB, default=dict)  # 存储用户回答
    status: Mapped[str] = mapped_column(default="in_progress")  # in_progress / completed / abandoned
    completed_steps: Mapped[list[int]] = mapped_column(JSONB, default=list)  # 已完成步骤
```

#### 3.1.3 修改：`Project` 表

```python
# models/project.py
class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    # ... 现有字段 ...
    world_building_completed: Mapped[bool] = mapped_column(default=False)  # 新增：引导式世界观是否完成
    initial_idea: Mapped[Optional[str]] = mapped_column(Text)  # 新增：用户初始想法
```

#### 3.1.4 新增：审阅反馈表

```python
# models/chapter_review_feedback.py（新建）
class ChapterReviewFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_review_feedbacks"

    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    feedback_type: Mapped[str] = mapped_column()  # "revision_request" / "manual_edit" / "approval"
    content: Mapped[Optional[str]] = mapped_column(Text)  # 用户反馈内容
    version_number: Mapped[int] = mapped_column()  # 针对哪个版本
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

---

### 3.2 新增服务层

#### 3.2.1 引导式世界观服务

参考 `style_analysis_service.py` 的实现模式，使用 `model_gateway` 调用 Gemini 模型：

```python
# services/world_building_service.py（新建）

from agents.model_gateway import GenerationRequest, model_gateway

STEP_CONFIGS = {
    1: {
        "title": "世界基底",
        "initial_question": "请问，这是一个什么样的世界？",
        "follow_up_template": """你描述了一个{summary}的世界。
那我想进一步了解：

1. {q1}
2. {q2}
3. {q3}
4. {q4}""",
        "expansion_q1": "这个世界的核心规则是什么？",
        "expansion_q2": "这个世界的主要特色是什么？",
        "expansion_q3": "这个世界的时间跨度有多长？",
        "expansion_q4": "有没有什么独特的历史节点？",
    },
    # ... 其他步骤配置
}

# 步骤1的模型 Prompt 模板
WORLD_BASE_SYSTEM_PROMPT = """你是一位资深的小说世界观架构师。你的任务是引导用户完善他们的世界观设定。

工作方式：
1. 用户回答你的初始问题后，先总结用户描述的世界特征
2. 然后主动扩展，追问 3-4 个能加深世界深度的具体问题
3. 每次只追问一个问题链，保持对话聚焦
4. 根据用户的回答，你要有自己的判断和联想，不要只是记录

输出格式（纯文本）：
[你的总结]
追问：{问题}

保持专业、有深度、善于联想的风格。"""

WORLD_BASE_USER_PROMPT = """用户说：{user_input}

请先总结用户描述的世界特征，然后追问你认为最重要的问题。"""


@dataclass
class WorldBuildingStepResponse:
    step: int
    model_expansion: str  # 模型的追问内容
    user_summary: str     # 模型对用户回答的总结
    is_awaiting_follow_up: bool  # 是否在等待用户追问后的确认
    suggested_next_step: int     # 建议的下一步


class WorldBuildingService:
    """引导式世界观生成服务"""

    STEPS = [
        {"step": 1, "key": "world_base", "title": "世界基底", "required": True},
        {"step": 2, "key": "physical_world", "title": "物理世界", "required": True},
        {"step": 3, "key": "power_system", "title": "力量体系", "required": True},
        {"step": 4, "key": "society", "title": "社会结构", "required": True},
        {"step": 5, "key": "protagonist", "title": "主角定位", "required": True},
        {"step": 6, "key": "core_conflict", "title": "核心冲突", "required": True},
        {"step": 7, "key": "world_details", "title": "世界细节", "required": False},
        {"step": 8, "key": "style_preference", "title": "风格偏好", "required": False},
    ]

    async def start_session(
        self,
        session: AsyncSession,
        project: Project,
        user_id: UUID,
        initial_idea: str,
    ) -> WorldBuildingSession:
        """开始新的引导会话，创建 WorldBuildingSession 记录"""

    async def process_step(
        self,
        session: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        step: int,
        user_input: str,
    ) -> WorldBuildingStepResponse:
        """
        处理用户输入，返回模型扩展后的追问
        使用 gemini-3.1-pro-preview

        实现参考 style_analysis_service.py：
        1. 构建 GenerationRequest
        2. 调用 model_gateway.generate_text()
        3. 解析返回内容
        """

    async def generate_blueprint(
        self,
        session: AsyncSession,
        project: Project,
        user_id: UUID,
    ) -> ProjectNovelBlueprintRead:
        """
        基于收集的信息生成大纲
        调用现有的 project_bootstrap_service.generate_project_blueprint()
        """


# services/world_building_session.py（新建）
# WorldBuildingSession 模型

class WorldBuildingSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    引导式世界观生成会话

    用户行为设计：
    - 用户随时可以退出，会话状态自动保存
    - 用户再次进入时，从 last_active_step 继续
    - 已完成的步骤数据保存在 session_data 中
    """
    __tablename__ = "world_building_sessions"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    current_step: Mapped[int] = mapped_column(default=1)  # 1-8 对应引导步骤
    last_active_step: Mapped[int] = mapped_column(default=1)  # 用户最后活跃步骤，用于恢复
    session_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # session_data 结构示例：
    # {
    #     "initial_idea": "修仙世界，主角废物流崛起",
    #     "step_1": {
    #         "user_input": "修仙世界，有宗门、灵根、飞升体系",
    #         "model_expansion": "追问内容...",
    #         "follow_up": "用户继续回答...",
    #         "completed": true
    #     },
    #     "step_2": {...},
    #     ...
    # }
    status: Mapped[str] = mapped_column(default="in_progress")
    completed_steps: Mapped[list[int]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

#### 3.2.2 写作意图服务

```python
# services/writing_intent_service.py（新建）

class WritingIntentService:
    """章节写作意图服务"""

    async def generate_intent(
        self,
        session: AsyncSession,
        chapter: Chapter,
        project: Project,
        user_id: UUID,
    ) -> str:
        """
        基于章节细纲生成写作意图（100-300字）
        使用 gemini-3.1-pro-preview
        """

    async def update_intent(
        self,
        session: AsyncSession,
        chapter_id: UUID,
        user_id: UUID,
        writing_intent: str,
    ) -> Chapter:
        """用户修改写作意图"""

    async def approve_intent(
        self,
        session: AsyncSession,
        chapter_id: UUID,
        user_id: UUID,
    ) -> Chapter:
        """用户确认写作意图，触发生成"""
```

#### 3.2.3 审阅反馈服务

```python
# services/chapter_review_service.py（新建）

class ChapterReviewService:
    """章节审阅反馈服务"""

    async def submit_revision_request(
        self,
        session: AsyncSession,
        chapter_id: UUID,
        user_id: UUID,
        feedback: str,
    ) -> ChapterReviewFeedback:
        """用户提交修订请求"""

    async def process_revision(
        self,
        session: AsyncSession,
        chapter_id: UUID,
        user_id: UUID,
        feedback: str,
    ) -> Chapter:
        """Agent 处理修订请求，重新生成"""
```

---

### 3.3 API 设计

#### 3.3.1 引导式世界观 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/v1/projects/{project_id}/world-building/start` | POST | 开始引导会话 |
| `/api/v1/projects/{project_id}/world-building/step/{step}` | POST | 处理第 N 步 |
| `/api/v1/projects/{project_id}/world-building/session` | GET | 获取当前会话状态 |
| `/api/v1/projects/{project_id}/world-building/generate-blueprint` | POST | 基于收集的信息生成大纲 |
| `/api/v1/projects/{project_id}/world-building/abandon` | POST | 放弃当前会话 |

#### 3.3.2 写作意图 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/v1/chapters/{chapter_id}/writing-intent` | GET | 获取章节写作意图 |
| `/api/v1/chapters/{chapter_id}/writing-intent` | PUT | 用户修改写作意图 |
| `/api/v1/chapters/{chapter_id}/writing-intent/approve` | POST | 确认写作意图，触发生成 |

#### 3.3.3 审阅反馈 API

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/v1/chapters/{chapter_id}/review/feedback` | POST | 提交审阅反馈 |
| `/api/v1/chapters/{chapter_id}/review/history` | GET | 获取审阅历史 |
| `/api/v1/chapters/{chapter_id}/review/manual-edit` | PATCH | 标记为手动编辑 |
| `/api/v1/chapters/{chapter_id}/review/approve` | POST | 直接通过 |

#### 3.3.4 Agent 反馈格式设计

用户反馈给 Agent 时，使用 Markdown 格式，确保大模型最容易理解和执行：

```markdown
## 修订指令

### 目标章节
- 章节编号：{chapter_number}
- 章节标题：{chapter_title}
- 版本号：{version_number}

### 当前问题
{用户描述的问题，如"主角反应不合理"、"打斗场景太平淡"}

### 修改要求
{用户的具体修改要求，如"让主角更隐忍一些"、"增加一些环境描写"}

### 上下文参考
- 写作意图：{writing_intent}
- 细纲摘要：{outline_summary}
- 世界观设定：{relevant_story_bible_entries}

### 输出要求
1. 直接输出修改后的正文
2. 不要解释修改了什么
3. 保持原有字数规模
```

### 3.4 前端页面设计

#### 3.4.1 引导式世界观生成页面

```
/dashboard/projects/{projectId}/world-building
```

**布局**：
```
┌────────────────────────────────────────────┐
│  步骤指示器 (1 → 2 → 3 → ... → 8)            │
├────────────────────────────────────────────┤
│                                            │
│  当前步骤：世界基底                          │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ 初始想法：我想写一个修仙世界...         │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ AI 追问：灵根是天生的还是后天获取？      │  │
│  │          宗门之外还有什么势力？         │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ 用户回答：                             │  │
│  │ [                                    ] │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  [上一步]  [下一步]  [跳过此步]  [退出]     │
│                                            │
└────────────────────────────────────────────┘
```

**状态管理**：
- `currentStep`: number (1-8)
- `sessionData`: Record<string, string> // 各步骤的回答
- `isLoading`: boolean
- `modelExpansions`: string[] // 模型追问内容
- `userAnswers`: string[] // 用户回答历史

#### 3.4.2 章节写作意图确认页面

**复用 story-room 页面**，在现有布局基础上增加：

```
┌────────────────────────────────────────────┐
│  章节 12：破茧成蝶                           │
├────────────────────────────────────────────┤
│  细纲：                                     │
│  - 目标：主角突破境界                        │
│  - 摘要：...                                │
├────────────────────────────────────────────┤
│  ✏️ 写作意图（由 AI 生成）                  │
│  ┌──────────────────────────────────────┐  │
│  │ 本章计划从主角被迫离开家乡切入，通过    │  │
│  │ 回忆展现师徒羁绊，为后续背叛埋线。      │  │
│  │ 采用倒叙与现实交织的手法...            │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  [修改意图]  [确认并开始写]  [返回大纲]      │
└────────────────────────────────────────────┘
```

#### 3.4.3 审阅反馈界面

**复用 story-room 页面**，在现有 `ChapterReviewPanel` 基础上扩展：

```
┌────────────────────────────────────────────┐
│  审阅面板                                   │
├────────────────────────────────────────────┤
│  版本 3 | 状态：待审阅                      │
├────────────────────────────────────────────┤
│  [✓ 通过]  [✏️ 手动改]  [🔄 反馈给 Agent]   │
├────────────────────────────────────────────┤
│  反馈给 Agent（可选）：                      │
│  ┌──────────────────────────────────────┐  │
│  │ [                                    ] │  │
│  │ [                                    ] │  │
│  └──────────────────────────────────────┘  │
│  [提交反馈并重新生成]                        │
└────────────────────────────────────────────┘
```

---

## 四、关键交互设计

### 4.1 引导式世界观生成流程

```
用户输入初始想法
      ↓
创建 WorldBuildingSession
      ↓
┌─────────────────────────────────┐
│  Step 1: 世界基底                │
│  AI: "这是一个什么样的世界？"      │
│  用户: "修仙世界，有宗门..."       │
│  AI 扩展追问（自动）              │
│  用户: 继续回答                   │
│  [下一步] → Step 2               │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  Step 2-8: 递进式引导            │
│  （模型记住上下文，保证自洽）      │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  完成 8 步后                     │
│  用户可选择：                    │
│  - [生成大纲] → 生成 chapter_blueprints │
│  - [继续补充] → 回到某一步重新回答      │
└─────────────────────────────────┘
      ↓
更新 Project.bootstrap_profile
更新 Project.novel_blueprint
标记 Project.world_building_completed = True
```

### 4.2 写作意图确认流程

```
用户选择章节 → 进入章节详情
      ↓
检查 Chapter.writing_intent
      ↓
┌─────────────────────────────────┐
│  如果没有意图：                  │
│  AI 基于细纲生成意图（100-300字） │
│  用户确认/修改                   │
│  [确认] → 触发 Agent 生成       │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  如果有意图但未确认：             │
│  显示已有意图                    │
│  用户可 [修改意图] 或 [直接确认]  │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  如果已确认：                    │
│  显示意图和当前生成状态          │
│  用户可 [查看生成进度]           │
└─────────────────────────────────┘
```

### 4.3 审阅循环流程

```
Agent 集群生成章节
      ↓
展示给用户审阅
      ↓
┌──────────┬──────────┬──────────┐
│  ✓ 通过   │ ✏️ 手动改  │ 🔄 反馈  │
└──────────┴──────────┴──────────┘
      │         │         │
      ↓         ↓         ↓
  保存版本   用户直接编辑  提交反馈
  status=   content=     调用 Agent
  approved  用户编辑内容   重新生成
                            ↓
                      ┌──────────┐
                      │ 新版本   │
                      │ 循环审阅 │
                      └──────────┘
```

---

## 五、与现有系统的集成

### 5.1 与 `story_engine_workflow_service` 的关系

- 引导式世界观生成完成后，结果写入 `Project.bootstrap_profile`
- 生成章纲时调用现有的 `generate_project_blueprint()`
- 写作意图确认后，触发 `dispatch_next_project_chapter_generation()`

### 5.2 与 `CanonGuardianAgent` 的关系

- 新增"圣经冲突检测"能力
- 在写作意图生成和章节生成前，检查内容是否符合 `StoryBible`
- 若冲突，提示用户并阻止生成

### 5.3 与 `project_bootstrap_service` 的关系

- 引导式世界观完成后，更新 `ProjectBootstrapProfile`
- 复用现有的 `update_project_bootstrap_profile()` 逻辑

---

## 六、实现计划

### Phase 1: 基础数据模型
1. 新增 `WorldBuildingSession` 模型
2. 新增 `ChapterReviewFeedback` 模型
3. 修改 `Chapter` 表增加 `writing_intent` 字段
4. 修改 `Project` 表增加 `world_building_completed` 和 `initial_idea`

### Phase 2: 后端服务
1. 实现 `WorldBuildingService` - 引导式世界观生成
2. 实现 `WritingIntentService` - 写作意图生成和确认
3. 实现 `ChapterReviewService` - 审阅反馈循环
4. 新增 API 路由

### Phase 3: 前端页面
1. 新建 `/world-building` 页面 - 引导式世界观 UI
2. 修改 story-room 页面 - 增加写作意图确认
3. 修改 ChapterReviewPanel - 增加反馈 Agent 功能

### Phase 4: 集成测试
1. 端到端流程测试
2. 冲突检测测试
3. 性能测试

---

## 七、已确认事项

1. **引导步骤不可定制** - 固定 8 步引导流程
2. **用户中途退出的处理** - 保存已回答的内容和生成结果，用户再次进入时从退出的问题继续
3. **反馈给 Agent 的内容格式** - 使用大模型最容易识别的 Markdown 格式，包含结构化指令和上下文
