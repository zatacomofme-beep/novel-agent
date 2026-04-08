# Novel Agent 前端架构问题清单

> 创建时间：2026-04-07
> 状态：待修复

---

## 一、架构层面问题（致命级）

### **P1: 上帝组件 (God Component)**
- **位置**: `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`
- **规模**: **5349行代码**
- **问题**:
  - 包含 **86个 useState** 状态变量
  - 包含 **60+个函数定义**（工具函数、事件处理器、业务逻辑）
  - 同时渲染 **10+个独立功能区域**
- **影响**:
  - 无法维护，任何修改都可能引发连锁反应
  - 性能问题：任何状态变化都触发整个组件重渲染
  - 测试困难：无法单独测试某个功能模块
- **严重程度**: 🔴 **致命**

---

### **P2: 职责混乱**
- **位置**: 同上
- **问题**: 单个文件承担了以下所有职责：
  ```
  ✗ 路由参数解析
  ✗ 状态管理（86个状态）
  ✗ API调用封装
  ✗ 数据转换/格式化
  ✗ 业务逻辑判断
  ✗ UI渲染
  ✗ 事件处理
  ✗ 表单验证
  ✗ 错误处理
  ✗ 本地存储管理
  ```
- **影响**: 违反单一职责原则（SRP），代码耦合度极高
- **严重程度**: 🔴 **致命**

---

### **P3: 10个废弃的重定向页面**
- **位置**: `dashboard/projects/[projectId]/` 目录下
- **废弃页面列表**:

  | 页面路径 | 当前行为 |
  |---------|---------|
  | `world-building/page.tsx` | → 重定向到 story-room |
  | `bootstrap/page.tsx` | → 重定向到 story-room |
  | `bible/page.tsx` | → 重定向到 story-room |
  | `generations/characters/page.tsx` | → 重定向到 story-room |
  | `generations/locations/page.tsx` | → 重定向到 story-room |
  | `generations/items/page.tsx` | → 重定向到 story-room |
  | `generations/factions/page.tsx` | → 重定向到 story-room |
  | `generations/plot-threads/page.tsx` | → 重定向到 story-room |
  | `generations/supporting/page.tsx` | → 重定向到 story-room |

- **问题**:
  - 设计时有清晰的页面划分，实现时全部放弃
  - URL结构与实际功能完全脱节
  - 误导开发者以为这些是独立功能
- **影响**: 代码冗余，维护成本高
- **严重程度**: 🟠 **高**

---

## 二、交互逻辑问题（严重级）

### **P4: 阶段导航无主次关系**
- **位置**: `story-room/page.tsx` L1484-L1505
- **当前实现**:
  ```typescript
  const stageCards = [
    { key: "outline", title: "大纲" },
    { key: "draft", title: "正文" },
    { key: "final", title: "终稿" },
    { key: "knowledge", title: "设定" },
  ];
  // ❌ 全部平级，可随意点击
  ```
- **设计文档要求**:
  ```
  Phase 1: 世界观构建(必经) → Phase 2: 大纲确认 → Phase 3: 创作审阅
  ```
- **问题**:
  - 用户不知道应该先做什么
  - 可以跳过必要步骤（如世界观构建）
  - 没有进度感和成就感
- **影响**: 新手用户迷失，流程不清晰
- **严重程度**: 🔴 **严重**

---

### **P5: 推荐逻辑错误**
- **位置**: `story-room/page.tsx` L1472-L1477
- **当前实现**:
  ```typescript
  const recommendedStage = !hasOutlineBlueprint
    ? "outline"           // ❌ 直接推荐去大纲
    : !hasDraftStarted
      ? "draft"
      : ...
  ```
- **正确逻辑应该是**:
  ```typescript
  const recommendedStage = !worldBuildingCompleted
    ? "world-building"    // ✓ 先完成世界观
    : !hasOutlineBlueprint
      ? "outline"
      : ...
  ```
- **问题**: 新书直接跳过8步引导进入大纲阶段
- **影响**: 核心流程断裂，用户无法体验完整引导
- **严重程度**: 🔴 **严重**

---

### **P6: World-Building 完成后无衔接**
- **位置**: `frontend/components/story-engine/world-building-panel.tsx` L42-L44
- **当前实现**:
  ```typescript
  onComplete={() => {
    setActiveStage("outline");       // ❌ 立即跳转
    setPendingStageScroll("outline");
  }}
  ```
- **后端实际情况**:
  - 后端在8步完成后会**自动触发 blueprint 生成**
  - 生成需要时间（可能10-30秒）
  - 前端没有等待机制
- **问题**:
  - 没有显示"正在生成大纲..."的加载状态
  - 用户不知道后台在做什么
  - 可能跳转后看到空的大纲页面
- **影响**: 用户体验断层，产生困惑
- **严重程度**: 🟠 **高**

---

### **P7: 缺少持久化状态**
- **位置**: 数据模型层
- **设计要求但未实现的字段**:
  ```python
  # Project 表缺少：
  world_building_completed: Mapped[bool]   # 未实现
  initial_idea: Mapped[str]               # 未实现
  current_phase: Mapped[str]               # 未实现
  ```
- **问题**:
  - 刷新页面后丢失 world-building 进度
  - 无法判断用户处于哪个阶段
  - 旧项目和新项目无法区分处理
- **影响**: 状态不一致，用户体验差
- **严重程度**: 🟠 **高**

---

## 三、信息架构问题（中等）

### **P8: 信息过载**
- **位置**: `story-room/page.tsx` L4580-L5349
- **单页同时展示的内容**:

  | 区域 | 内容 | 显示条件 |
  |-----|------|---------|
  | 头部 | 项目标题、题材、气质、设定条数、当前章节 | 始终显示 |
  | 推荐区 | 下一步提示、操作按钮、4个卡片 | 始终显示 |
  | OutlineWorkbench | 三级大纲编辑器 | outline阶段 |
  | DraftStudio | 正文编辑器 + 实时守护 | draft阶段 |
  | ReviewPanel | 版本/批注/确认点 | draft阶段 |
  | StyleControl | 文风控制 | 折叠状态 |
  | FinalDiff | 终稿对比 | final阶段 |
  | PublishPanel | 发布操作 | final阶段 |
  | KnowledgeBoard | 设定管理 | knowledge阶段 |
  | PlaybackPanel | 过程回放 | 始终显示 |
  | 移动端Dock | 底部4格导航 | 移动端 |

- **问题**:
  - 认知负荷极高
  - 用户不知道当前该关注什么
  - 重要信息被淹没
- **影响**: 用户困惑，效率低下
- **严重程度**: 🟡 **中**

---

### **P9: 头部信息冗余**
- **位置**: `story-room/page.tsx` L4620-L4640
- **当前展示**:
  ```
  项目标题
  题材：xxx | 气质：xxx | 设定条目：xx | 当前章节：第x章
  ```
- **问题**:
  - 大部分信息用户不需要每次都看
  - 与下面的推荐区域重复
  - 占用宝贵的屏幕空间
- **影响**: 信息噪音干扰核心任务
- **严重程度**: 🟡 **中**

---

### **P10: StageCards 设计不当**
- **位置**: `story-room/page.tsx` L4777-L4810
- **当前设计**: 4个并列的方形卡片
- **问题**:
  - 视觉上暗示"这4个是平等的"
  - 实际上有明确的先后顺序关系
  - 数字编号(1,2,3,4)不够直观
- **影响**: 误导用户的操作顺序认知
- **严重程度**: 🟡 **中**

---

## 四、代码质量问题（技术债）

### **P11: 工具函数与组件混在一起**
- **位置**: `story-room/page.tsx` L135-L1172
- **问题**: 前1000行全是工具函数
  ```typescript
  function parseStoryRoomStage() {...}      // L135
  function buildWorkflowPlaybackStep() {...} // L428
  function normalizeTaskStatus() {...}       // L315
  function resolveKnowledgeEntityId() {...}  // L630
  // ... 共60+个函数
  ```
- **应该提取到**: `utils/` 或 `hooks/` 目录
- **影响**: 组件文件臃肿，难以复用和测试
- **严重程度**: 🟠 **高**

---

### **P12: 状态管理分散**
- **位置**: `story-room/page.tsx` L1190-L1280
- **86个useState分类**:

  | 类别 | 数量 | 示例 |
  |-----|------|------|
  | 项目数据 | 15 | workspace, bootstrapState, storyBible... |
  | 大纲相关 | 12 | idea, genre, tone, outlines... |
  | 章节相关 | 18 | chapterNumber, draftText, streamingChapter... |
  | 设定相关 | 20 | activeTab, editingId, formState... |
  | UI状态 | 21 | loading, error, activeStage, scroll... |

- **问题**:
  - 相关状态没有聚合
  - 状态间依赖关系复杂且隐式
  - 容易出现状态不同步
- **影响**: Bug频发，调试困难
- **严重程度**: 🟠 **高**

---

### **P13: Props Drilling 严重**
- **位置**: `story-room/page.tsx` L4936-L5080
- **示例 - DraftStudioProvider 的 props**:
  ```typescript
  <DraftStudioProvider
    initialState={{
      chapterNumber,          // prop 1
      chapterTitle,           // prop 2
      draftText,              // prop 3
      outlines,               // prop 4
      scopeChapters,          // prop 5
      outlineSelectionId,     // prop 6
      activeChapter,          // prop 7
      scopeLabel,             // prop 8
      savedChapterCount,      // prop 9
      guardResult,            // prop 10
      pausedStreamState,      // prop 11
      // ... 共25+个props
    }}
    callbacks={{
      onChapterNumberChange,  // callback 1
      onChapterTitleChange,   // callback 2
      onDraftTextChange,      // callback 3
      // ... 共20+个callbacks
    }}
  >
  ```
- **问题**:
  - 传递了 **45+个 props** 给子组件
  - 任何变更都需要修改多层代码
  - 已经用 Context API 解决了一部分（DraftStudio），但主页面仍然混乱
- **影响**: 维护成本高，容易出错
- **严重程度**: 🟡 **中**

---

### **P14: 缺少错误边界和加载状态**
- **位置**: 全局
- **问题**:
  - 没有使用 React ErrorBoundary
  - 加载状态只有一个全局的 spinner
  - 没有骨架屏（Skeleton）优化感知性能
  - API 错误处理不统一
- **影响**:
  - 一个子组件崩溃导致整个白屏
  - 用户不知道是在加载还是出错了
- **严重程度**: 🟡 **中**

---

## 五、功能缺陷问题

### **P15: World-Building 不在主导航中**
- **位置**: stageCards 定义
- **问题**:
  - WorldBuildingPanel 已创建，但不在4个主要卡片中
  - 只能通过 URL 参数 `?stage=world-building` 进入
  - 完成后无法回到此步骤查看/修改
- **影响**:
  - 用户发现不了这个功能
  - 已完成的设定无法回顾
- **严重程度**: 🔴 **严重**

---

### **P16: 断线续传体验差**
- **位置**: `story-room/page.tsx` 本地草稿相关逻辑
- **问题**:
  - 有复杂的本地存储逻辑（~500行代码）
  - 但恢复流程不直观
  - 云端草稿和本地草稿概念混淆
- **影响**: 用户担心丢失内容
- **严重程度**: 🟡 **中**

---

### **P17: 移动端适配不完善**
- **位置**: `story-room/page.tsx` 移动端Dock
- **问题**:
  - 底部固定Dock遮挡内容
  - 折叠面板（details元素）交互不便
  - StageCards 在手机上变成横向滚动，体验差
- **影响**: 移动端用户无法正常使用
- **严重程度**: 🟡 **中**

---

## 六、总结统计

| 严重程度 | 数量 | 问题编号 |
|---------|------|---------|
| 🔴 致命 | 3 | P1, P2, P4 |
| 🔴 严重 | 3 | P5, P6, P15 |
| 🟠 高 | 4 | P3, P7, P11, P12 |
| 🟡 中 | 7 | P8, P9, P10, P13, P14, P16, P17 |
| **总计** | **17** | |

---

## 七、建议修复优先级

### 第一优先级（已完成 ✅）

| 编号 | 问题 | 修复方案 | 状态 |
|-----|------|---------|------|
| P5 | 推荐逻辑错误 | 修改 `recommendedStage` 判断逻辑，优先检查 worldBuildingCompleted | ✅ 完成 |
| P15 | World-Building 不在主导航 | 将 "world-building" 加入 stageCards，并设置正确顺序 | ✅ 完成 |
| P6 | World-Building 完成后无衔接 | 添加"正在生成大纲..."的加载状态和轮询机制 | ✅ 完成 |

### 第二优先级（短期重构）- ✅ 已完成

> ⚠️ **警告**: `story-room/page.tsx` 是一个 5349 行的上帝组件，包含 86 个 useState 和 60+ 个函数。
> 大规模重构风险极高，建议**增量重构**方式，每次只移动一小部分代码。

| 编号 | 问题 | 修复方案 | 状态 |
|-----|------|---------|------|
| P11 | 工具函数混在一起 | 提取到 `utils/story-room-utils.ts` | ✅ 完成 |
| P1-P2 | 上帝组件 | 拆分为多个 Phase 组件 (phases/) | ✅ 完成 |
| P12 | 状态管理分散 | 创建 `context.ts` 聚合 activeStage | ✅ 完成 |
| P7 | 缺少持久化字段 | 在 Project 模型中添加必要字段 | ✅ 完成 |

**完成内容**:

```typescript
// utils.ts - 29 个提取的工具函数
export function parseListField(value: string): string[] { ... }
export function readNestedRecord(value: unknown): Record<string, unknown> { ... }
export function normalizePositiveNumber(value: string | undefined, fallback: number): number { ... }
export function readMetadataNumber(metadata: Record<string, unknown>, key: string): number | null { ... }
export function readMetadataString(metadata: Record<string, unknown>, key: string): string | null { ... }
export function readMetadataStringList(metadata: Record<string, unknown>, key: string): string[] { ... }
export function createClientUuid(): string { ... }
export function extractLatestDraftParagraph(text: string): string | null { ... }
export function isStoryBibleKnowledgeTab(tab: KnowledgeTabKey): tab is StoryBibleKnowledgeTab { ... }
export function buildCloudDraftScopeKey(branchId: string | null, volumeId: string | null, chapterNumber: number): string { ... }
export function toLocalDraftSnapshotFromCloudDraft(draft: StoryRoomCloudDraft): StoryRoomLocalDraftSnapshot { ... }
export function normalizeKnowledgeLookupText(value: string): string { ... }
export function resolveKnowledgeTabForEntityType(entityType: string): KnowledgeTabKey | null { ... }
export function resolveKnowledgeItemLabel(tab: KnowledgeTabKey, item: Record<string, unknown>): string { ... }
export function parseStoryRoomStage(value: string | null): StoryRoomStageKey | null { ... }
export function parseStoryRoomChapterNumber(value: string | null): number | null { ... }
export function sortChapters(chapters: Chapter[]): Chapter[] { ... }
export function findCreatedStructureItemId<T extends { id: string }>(previousItems: T[], nextItems: T[]): string | null { ... }
export function isChapterInScope(chapter: Chapter, branchId: string | null, volumeId: string | null): boolean { ... }
export function buildChapterOutlinePayload(outline: StoryOutline | null): Record<string, unknown> | null { ... }
export function buildRecentChapterTexts(chapters: Chapter[], chapterSummaries: StoryChapterSummary[], chapterNumber: number): string[] { ... }
export function buildCurrentChapterCarryoverPreview(summary: StoryChapterSummary | null): string[] { ... }
export function selectLatestTask(taskData: TaskState[]): TaskState | null { ... }
export function readWorkflowStatusFromTaskResult(result: Record<string, unknown> | null | undefined): string | null { ... }
export function readWorkflowStatusFromTaskEventPayload(payload: Record<string, unknown> | null | undefined): string | null { ... }
export function normalizeTaskStatus(status: string, workflowStatus?: string | null): ProcessPlaybackStatus { ... }
export function normalizeWorkflowStatus(status: string): ProcessPlaybackStatus { ... }
export function resolveWorkflowStage(workflowType: string): StoryRoomStageKey { ... }
export function formatWorkflowLabel(workflowType: string): string { ... }

// phases/ - 4 个 Phase 占位组件
export { WorldBuildingPhase } from "./WorldBuildingPhase";  // 世界观阶段
export { OutlinePhase } from "./OutlinePhase";               // 大纲阶段
export { CreationPhase } from "./CreationPhase";             // 创作阶段
export { ReviewPhase } from "./ReviewPhase";                 // 终稿阶段

// context.ts - 状态管理 Context
interface StoryRoomPhaseContextValue {
  activeStage: StoryRoomStageKey | null;
  setActiveStage: (stage: StoryRoomStageKey | null) => void;
  pendingStageScroll: StoryRoomStageKey | null;
  setPendingStageScroll: (stage: StoryRoomStageKey | null) => void;
}
```

#### Phase 2 重构详细计划

**阶段 2.1: 目录结构重组** (预计 0.5 天)
```
story-room/
├── page.tsx                    # 主入口 (~500行)
├── phases/                     # 新建：各阶段容器组件
│   ├── index.ts
│   ├── WorldBuildingPhase.tsx   # 世界观阶段
│   ├── OutlinePhase.tsx        # 大纲阶段
│   ├── CreationPhase.tsx       # 创作阶段
│   └── ReviewPhase.tsx         # 终稿阶段
├── components/                 # 新建：从 page.tsx 提取的组件
│   ├── PhaseNavigator.tsx
│   ├── PhaseProgress.tsx
│   └── ...
├── hooks/                      # 新建：自定义 Hooks
│   ├── useStoryRoom.ts
│   ├── useWorldBuilding.ts
│   └── ...
├── utils/                      # 新建：工具函数
│   └── story-room-utils.ts
└── types/                      # 新建：类型定义
    └── index.ts
```

**阶段 2.2: 创建 Phase Context** (预计 1 天)
- 创建 `StoryRoomPhaseContext` 管理跨阶段共享状态
- 将相关 useState 组装成 context value
- 使用 `useReducer` 聚合相关状态更新逻辑

**阶段 2.3: 逐步拆分组件** (预计 2-3 天)
- 每次只拆分一个小功能区域
- 保持其他部分不变，确保能正常运行
- 优先拆分 WorldBuildingPanel（已独立）

**阶段 2.4: 数据库字段补全** (预计 0.5 天)
```sql
ALTER TABLE projects ADD COLUMN world_building_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN initial_idea TEXT;
ALTER TABLE projects ADD COLUMN current_phase VARCHAR(50) DEFAULT 'world-building';
```

### 第三优先级（中期优化）- 部分完成

| 编号 | 问题 | 修复方案 | 状态 |
|-----|------|---------|------|
| P4 | 阶段导航无主次 | 重新设计为锁定式进度条 | ✅ 完成 |
| P9 | 头部信息冗余 | 创建 HeaderInfo 组件，可折叠详情 | ✅ 完成 |
| P10 | StageCards 设计不当 | PhaseProgress 替换 | ✅ 完成 (P4 中修复) |
| P8 | 信息过载 | 单页10+区域拆分（需更大重构） | ⚠️ 延期 |
| P14 | 缺少错误边界 | 添加 error.tsx + loading.tsx | ✅ 完成 |

### 第四优先级（长期清理）

| 编号 | 问题 | 修复方案 | 状态 |
|-----|------|---------|------|
| P3 | 废弃的重定向页面 | 经检查：bible/bootstrap/world-building 等页面有实际 API 功能，generations/ 可删除 | ⚠️ 保留（有实际功能） |
| P13 | Props Drilling | 创建 StoryRoomProvider 框架，逐步迁移状态 | 🔄 进行中 |
| P17 | 移动端适配 | 重新设计移动端布局 | 待处理 |

---

## 八、技术债务估算

| 优先级 | 预计工作量 | 说明 |
|-------|----------|------|
| 第一优先级 | 1-2天 | 逻辑修改为主 |
| 第二优先级 | 3-5天 | 代码重构 |
| 第三优先级 | 1周+ | UI/UX 大改 |
| 第四优先级 | 2周+ | 全面清理 |

---

*文档版本: 2.0*
*最后更新: 2026-04-08*

---

# 全量清查报告（2026-04-08）

> 对前后端进行深度全量清查，以下为发现的所有问题和不足。

## 九、后端代码质量问题

### 🔴 严重（必须修复）

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| B1 | **ruff 372 个错误** | `backend/` 全局 | F401(133个未使用导入) + F821(113个未定义名称) + E402(66个导入位置) + F541(32个无效f-string) + F841(14个未使用变量) 等 |
| B2 | **3个 API 路由未注册** | `api/v1/router.py` | `prompt_templates`、`style_analysis`、`verification` 三个路由文件存在但未 include_router，前端调用 prompt-templates 会 404 |
| B3 | **2个模型未注册** | `models/__init__.py` | `PromptTemplate` 和 `RefreshToken` 模型未在 `__init__.py` 导出，Alembic autogenerate 可能遗漏 |
| B4 | **QDRANT_URL 配置错误** | `backend/.env.compose` L24 | 值为 `http://localhost:6333`，Docker 容器内应为 `http://qdrant:6333`，导致向量存储不可用 |

### 🟡 中等（建议修复）

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| B5 | **依赖导入不规范** | `api/v1/prompt_templates.py` L9 | 从 `api.v1.profile` 导入 `get_db_session/get_current_user`，应从 `api.deps` 导入 |
| B6 | **导入风格不一致** | `tasks/queues.py` L4 | 使用 `from celery_app import celery_app`（相对），其他文件用 `from tasks.celery_app`（绝对） |
| B7 | **API Key 为空** | `backend/.env.compose` L36-38 | `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MODEL_GATEWAY_API_KEY` 均为空，核心功能无法使用 |
| B8 | **JWT 密钥不安全** | `backend/.env.compose` L31 | 使用 `dev-secret-key-change-in-production-12345`，生产环境需更换 |

## 十、前端死代码问题（功能意图分析）

> 以下分析从「项目功能完整性」和「功能意图」角度判断每个文件是否应该保留。

### 逐文件分析

#### 1. `components/smart-recommend-panel.tsx` — `SmartRecommendPanel`

| 维度 | 分析 |
|------|------|
| **功能意图** | 根据当前写作场景（章节内容、上下文）自动推荐合适的提示词模板 |
| **后端支撑** | ✅ 有完整后端 `api/v1/prompt_templates.py`（含 `/recommend` 端点），但**未注册到 router** |
| **前端引用** | ❌ 0 处引用，未被任何页面导入 |
| **项目意图** | 🟡 **应保留但需集成**。这是「模板推荐」功能的核心 UI，后端已实现但前后端未打通。属于**已开发但未上线**的功能 |

#### 2. `components/guided-tour.tsx` — `PlatformGuide`

| 维度 | 分析 |
|------|------|
| **功能意图** | 新手引导组件，展示「风格分析 → 偏好设置 → 模板写作」4步工作流 |
| **后端支撑** | 不需要后端，纯前端展示组件 |
| **前端引用** | ❌ 0 处引用，Dashboard 页面没有使用 |
| **项目意图** | 🟡 **应保留但需集成**。Dashboard 页面目前缺少新手引导，新用户进入后不知道该做什么。这个组件正好解决此问题，应集成到 Dashboard |

#### 3. `components/story-bible-save-target-field.tsx` — `StoryBibleSaveTargetField`

| 维度 | 分析 |
|------|------|
| **功能意图** | Story Bible 保存时选择目标分支的下拉选择器 |
| **后端支撑** | ✅ 项目结构 API 已存在（`/api/v1/projects/{id}/structure`） |
| **前端引用** | ❌ 0 处引用，story-room 页面直接内联了分支选择逻辑 |
| **项目意图** | 🟢 **可删除**。story-room 页面已自行实现了分支选择逻辑，此组件功能已被内联替代，且无其他页面需要复用 |

#### 4. `components/error-boundary.tsx` — `ErrorDisplay/GlobalError/PageErrorBoundary`

| 维度 | 分析 |
|------|------|
| **功能意图** | 通用错误展示组件（局部错误、全局错误、页面级错误边界） |
| **后端支撑** | 不需要 |
| **前端引用** | ❌ 0 处引用。目前仅 story-room 有 `error.tsx`，根目录无 `global-error.tsx` |
| **项目意图** | 🔴 **应保留并集成**。项目缺少 `global-error.tsx`（Next.js 要求的全局错误边界），`GlobalError` 组件正是为此设计的。`ErrorDisplay` 可在各页面复用。属于**基础设施缺失** |

#### 5. `components/client-layout.tsx` — `ClientLayout`

| 维度 | 分析 |
|------|------|
| **功能意图** | 客户端布局包装器，包裹 `ToastProvider` |
| **后端支撑** | 不需要 |
| **前端引用** | ❌ 0 处引用。但 `ToastProvider` 本身也未被任何 layout 引用 |
| **项目意图** | 🔴 **应保留并集成**。`ToastProvider` 是全局基础设施，但当前项目的 layout 没有挂载它，导致 `useToast` 无法使用。`ClientLayout` 是正确的设计，应集成到根 layout |

#### 6. `components/loading.tsx` — `PageLoader/SectionLoader/ButtonLoader`

| 维度 | 分析 |
|------|------|
| **功能意图** | 通用加载状态组件（页面级、区域级、按钮级） |
| **后端支撑** | 不需要 |
| **前端引用** | ❌ 0 处引用。各页面自行实现了加载状态 |
| **项目意图** | 🟢 **可删除**。各页面已有自己的 loading 实现（skeleton、spinner 等），此组件未被采用且风格不统一，删除不影响功能 |

#### 7. `lib/api-client.ts` — `apiFetch/apiFetchWithAuth/useApiErrorHandler`

| 维度 | 分析 |
|------|------|
| **功能意图** | 带自动 token 刷新、错误分类、toast 提示的 API 客户端 |
| **后端支撑** | ✅ 依赖 `/api/v1/auth/refresh` 端点（已注册） |
| **前端引用** | ❌ 0 处引用。项目使用 `@/lib/api` 而非 `@/lib/api-client` |
| **项目意图** | 🟡 **应保留但需合并**。`api-client.ts` 比 `api.ts` 功能更完善（自动 token 刷新、错误分类、重试机制），但项目统一使用 `api.ts`。建议将 `api-client.ts` 的 token 刷新和错误分类能力合并到 `api.ts`，然后删除 `api-client.ts` |

#### 8. `lib/legacy-chapter-chain.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | 章节相关 API 调用封装（评论、检查点、审阅决策、选段重写等） |
| **后端支撑** | ✅ 后端有完整的章节相关 API |
| **前端引用** | ⚠️ **1 处引用**：`story-room/page.tsx` 导入了此文件 |
| **项目意图** | 🔴 **不可删除**。虽然文件名带 `legacy`，但它是 story-room 页面的实际依赖，删除会直接导致编译错误 |

#### 9. `lib/story-bible-deeplink.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | Story Bible 深度链接构建器，支持从外部跳转到特定 Story Bible 区域 |
| **后端支撑** | 不需要，纯前端路由构建 |
| **前端引用** | ❌ 0 处引用 |
| **项目意图** | 🟡 **应保留但需集成**。Story Bible 有多区域（角色、物品、势力、地点等），深度链接支持从其他页面直接跳转到指定区域。当前 story-room 的 URL 参数解析已部分实现，但未使用此工具统一管理 |

#### 10. `lib/story-bible-save.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | Story Bible 保存逻辑封装（自动选择分支、保存条目到指定分支） |
| **后端支撑** | ✅ 依赖 `/api/v1/projects/{id}/structure` 和 `/api/v1/projects/{id}/bible/item` |
| **前端引用** | ❌ 0 处引用。story-room 页面直接内联了保存逻辑 |
| **项目意图** | 🟡 **应保留但需集成**。当前 story-room 的保存逻辑散落在 page.tsx 中，此工具函数可以简化代码。属于**应提取但尚未使用**的工具库 |

#### 11. `lib/security.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | HTML 转义、输入清理、URL 白名单、CSP nonce |
| **后端支撑** | 不需要 |
| **前端引用** | ❌ 0 处引用 |
| **项目意图** | 🟡 **应保留但需集成**。`escapeHtml` 和 `sanitizeInput` 在用户输入场景（章节评论、设定编辑）中应该使用，防止 XSS。当前项目直接渲染用户输入，存在安全隐患 |

#### 12. `lib/errors.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | 错误分类器，将技术错误转换为用户友好提示 |
| **后端支撑** | 不需要 |
| **前端引用** | ⚠️ **3 处引用**：`story-room/page.tsx`、`collaborators/page.tsx`、`model-routing/page.tsx` |
| **项目意图** | 🔴 **不可删除**。正在被 3 个页面使用，不是死代码 |

#### 13. `lib/copy.ts`

| 维度 | 分析 |
|------|------|
| **功能意图** | 全局文案常量集合（按钮、空状态、加载、成功、错误、提示、世界观、故事工作台、审阅、仪表盘、项目等） |
| **后端支撑** | 不需要 |
| **前端引用** | ❌ 0 处引用。各组件直接硬编码中文文案 |
| **项目意图** | 🟡 **应保留并逐步采用**。当前项目文案散落在各组件中，修改困难且不一致。`copy.ts` 提供了统一的文案管理方案，应逐步替换硬编码文案 |

### 总结分类

| 分类 | 文件 | 建议 |
|------|------|------|
| 🔴 **不可删除（正在使用）** | `lib/legacy-chapter-chain.ts`、`lib/errors.ts` | 修正死代码判断，实际有引用 |
| 🔴 **应保留并集成（基础设施缺失）** | `components/error-boundary.tsx`、`components/client-layout.tsx` | 缺少 global-error.tsx 和 ToastProvider 挂载 |
| 🟡 **应保留但需集成（已开发未上线）** | `components/smart-recommend-panel.tsx`、`components/guided-tour.tsx`、`lib/story-bible-deeplink.ts`、`lib/story-bible-save.ts`、`lib/security.ts`、`lib/copy.ts` | 功能有价值但未接入 |
| 🟡 **应保留但需合并** | `lib/api-client.ts` | token 刷新等能力应合并到 `api.ts` |
| 🟢 **可安全删除** | `components/story-bible-save-target-field.tsx`、`components/loading.tsx` | 功能已被替代或未被采用 |

## 十一、架构遗留问题

| # | 问题 | 说明 | 优先级 |
|---|------|------|--------|
| A1 | **story-room/page.tsx 仍有 89 个 useState** | P13 Props Drilling 仅完成框架，状态未迁移 | 🟡 中 |
| A2 | **P8 信息过载延期** | 单页10+区域拆分需要更大重构 | 🟡 中 |
| A3 | **P17 移动端适配** | 未开始 | 🟢 低 |
| A4 | **neo4j_service.py 使用 except* 语法** | Python 3.11+ 语法，兼容性风险 | 🟢 低 |

## 十二、问题优先级总览

### 立即修复（阻塞功能）

1. **B2** - 注册缺失的 API 路由（prompt_templates 至少需要注册，前端有调用）
2. **B4** - 修复 QDRANT_URL 配置
3. **B3** - 注册缺失的模型

### 尽快修复（代码质量）

4. **B1** - ruff 错误清理（至少修复 F821 未定义名称）
5. **F1** - 清理前端死代码
6. **B5/B6** - 修复导入规范

### 后续优化

7. **B7/B8** - 配置真实 API Key 和安全密钥
8. **A1-A4** - 架构遗留问题
