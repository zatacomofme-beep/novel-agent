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

- 旧项目与旧版本记录里仍可能出现 `world_settings` wrapper，但运行时已改成原生优先，并会在读取时自动迁移/规范化

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

### 6. 实体生成接口已并入项目任务链

已修复：

- `/generations/*/dispatch` 现在会统一进入项目任务链，并回写 `task_runs` / `task_events`
- `entity_generation_service` 已接入项目级模型路由，按职责候选链自动选择模型
- 远程模型不可用或输出非法 JSON 时，会记录 failover / fallback 轨迹，而不是直接静默退回
- `story-room` 设定区已经能显示这条补全任务的阶段进度，而不只是一个最终结果

补充：

- 同步 `/generations/*` 路由仍然保留兼容能力
- 但写手主路径已经收口到 dispatch + task/event 的统一链路

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

### 9. `items / factions` 底层领域模型已完成第一版原生化

已修复：

- 项目级 `Story Bible` 读取时会自动把 legacy `world_settings` wrapper 迁移到原生 `project_items / project_factions`
- `build_public_story_bible_sections()` 已调整为 native-first，同名条目不会再被 legacy wrapper 反向覆盖
- 分支快照会在读取时 canonical 化为原生 section delta，不再继续把 `item / faction` 混在 `world_settings`
- 回滚版本时也会先做 canonical 化，避免旧 snapshot 恢复后重新污染主存储语义

补充：

- 兼容读取仍然保留，主要用于历史数据、导出和旧测试夹具，不再是主链写入策略

## 仍待处理

### P1: Story Bible 的溯源与引用关系还不够强

现象：

- 当前 `items / factions` 的主存储语义已经原生化
- 但正文引用、设定引用、分支差异来源、章节总结回写来源还没有形成统一的溯源关系层

影响：

- 当前前后端联调已经顺畅，领域存储也已经基本干净
- 但后续如果要做“正文引用某条设定时可回跳来源”“为什么这一条设定在分支里变了”这类能力，现有数据还不够可追踪

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

1. 先继续做 Story Bible 关联与溯源增强
2. 再决定旧章节编辑器哪些能力继续保留，哪些迁入 `story-room`

## 为什么这个顺序最合理

- 第一项现在不再是 API 契约或存储纯化问题，而是要把设定关系与来源链补齐
- 第二项虽然不直接改业务功能，但已经开始影响测试、导入和开发体验
