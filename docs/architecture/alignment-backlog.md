# 当前实现偏差与修复优先级

这份清单不是泛泛而谈的优化建议，而是基于当前代码观察到的实现偏差。
目标是帮助后续工作按优先级收口。

## 已完成收口

### 1. generation 保存 Story Bible 条目契约已对齐

已修复：

- generation 页面现已通过统一 helper 调用真实后端契约
- 请求带 `branch_id`
- 请求体改为 `{ section_key, item }`
- `items` / `factions` 现已作为公开 Story Bible section 写入，而不是再冒充 `world_settings`
- Bible 页面全量保存、分支单实体 patch、scope override 明细也已同步按 `items` / `factions` 暴露

仍需关注：

- 底层持久化仍然通过 `world_settings` wrapper 做兼容映射，不是最终领域表结构

### 2. pending count 路由已补齐

已修复：

- 后端已提供 `/api/v1/projects/{projectId}/bible/pending-changes/count`
- Bible 页面 pending 数量不再依赖不存在的接口

### 3. approve / reject 请求体已对齐

已修复：

- 前端现在显式发送 `StoryBibleApprovalRequest`
- reject 分支会要求输入驳回原因

### 4. approve pending change 已变为“批准并合并”

已修复：

- `approve_pending_change()` 现在会在同一条服务链里把提案应用到目标分支 Story Bible
- 实现复用了已有 `upsert_story_bible_branch_item()` / `delete_story_bible_branch_item()`
- 分支快照、版本记录、章节评估失效逻辑继续沿用原有主链

补充：

- 为了避免 `get_owned_project()` 的结构修复提交把 approved 状态提前落库，执行顺序已调整为先取项目、再改 pending 状态、再 apply

### 5. schema 导出兼容层已补回

已修复：

- `backend/schemas/base.py` 重新提供 `EmptyResponse` / `PaginatedResponse`
- `backend/schemas/__init__.py` 改为 lazy export，避免 eager import 触发循环依赖

### 6. 实体生成接口不再返回静态占位值

已修复：

- `/generations/characters`、`/items`、`/locations`、`/factions`、`/plot-threads`
  已接入 `entity_generation_service`
- 服务层优先走 `ModelGateway` 远程生成
- 远程模型不可用或输出非法 JSON 时，自动回退到本地启发式生成

补充：

- 当前是同步请求/响应式生成，不属于章节那条 task/event/agent 编排链
- 但已经不是 `角色1`、`物品1` 这类 scaffold 返回

### 7. story-room 已接入正式章节主链

已修复：

- `story-room` 会读取真实项目结构和真实章节列表
- 当前编辑区文本可以创建正式 `Chapter`
- 后续保存会走真实 `PATCH /chapters/{chapter_id}`
- 写作工作台右侧已能显示版本号、状态、基础 final gate 信息

补充：

- 这一步打通的是“写手主工作台 -> 正式章节链”的最小正确闭环
- 深度审校操作仍然主要保留在独立章节编辑器

### 8. 文档与基础设施认知已按新主形态收口

已修复：

- README 与 DEVELOPMENT 已改为围绕 `story-room`、正式章节主链和后台模型路由来描述
- 开发环境文件已拆分为本机直跑和 Docker Compose 两套语义
- 根目录 Compose 不再直接依赖 `backend/.env.example` 作为唯一真实配置
- 生产 Compose 已补齐 Chroma，并切换到生产 Dockerfile

补充：

- 模型路由现在明确被定义为后台管理员能力，而不是写手前台能力

## 仍待处理

### P1: 领域建模仍然不够纯

现象：

- `items`、`factions` 在公开 API 上已经是原生 section
- 但底层仍通过 `world_settings` 中的特殊 wrapper 行来持久化
- 这意味着 API 语义已经干净，数据库/领域模型仍保留兼容层

影响：

- 当前前后端联调已经顺畅
- 但数据库查询、迁移设计、后续 canon 编译优化仍然要背着兼容层做适配
- 如果后续要拆出真正的 `items` / `factions` 存储模型，还需要一次存储层迁移

相关代码：

- `frontend/app/dashboard/projects/[projectId]/bible/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/generations/items/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/generations/factions/page.tsx`
- `backend/schemas/project.py`
- `backend/services/project_service.py`

### P2: story-room 还没有完全吞下旧审校工作台

现象：

- 写手主工作台已经可以保存正式章节并看到基础 gate 状态
- 但评论、检查点、评审决议、回滚、片段重写等深度能力仍主要在旧编辑器页

影响：

- 前台主路径已经清晰
- 但“单工作台完成全部写作到放行”还没有彻底收口

相关代码：

- `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`
- `frontend/app/dashboard/editor/[chapterId]/page.tsx`
- `backend/api/v1/chapters.py`

## 建议修复顺序

1. 先决定 `items` / `factions` 是否继续从兼容存储升级到底层原生领域模型
2. 再决定实体生成是否要继续升级成 task/event/agent 化链路
3. 最后再决定旧章节编辑器哪些能力继续保留，哪些迁入 `story-room`

## 为什么这个顺序最合理

- 第一项现在不再是 API 契约问题，而是要不要继续推进到底层存储/领域模型纯化
- 第二项关系到 entity generation 是保持轻量同步服务，还是并入正式 Agent 工作流
- 第三项虽然不直接改业务功能，但已经开始影响测试、导入和开发体验
