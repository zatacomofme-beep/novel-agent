# Frontend/Backend API Contract Map

This document maps real frontend pages to real backend routes and service boundaries.
It also lists the main contract mismatches currently visible in code.

Primary route sources:
- `backend/api/v1/router.py`
- `backend/api/v1/projects.py`
- `backend/api/v1/chapters.py`
- `backend/api/v1/evaluation.py`
- `backend/api/v1/tasks.py`
- `backend/api/v1/dashboard.py`
- `backend/api/v1/profile.py`
- `backend/api/v1/story_engine.py`

Primary page sources:
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/preferences/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/chapters/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/bible/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/quality/page.tsx`
- `frontend/app/dashboard/editor/[chapterId]/page.tsx`

## 1. Router Topology

```text
/api/v1
 ├─ /auth
 ├─ /dashboard
 ├─ /profile
 ├─ /projects
 ├─ /chapters
 ├─ /evaluation
 ├─ /tasks
 └─ /story-engine

/ws
 └─ /tasks/{task_id}
```

## 2. Page-to-API Map

| Frontend page | Main requests | Backend route owner | Main backend service |
| --- | --- | --- | --- |
| `/dashboard` | `GET /dashboard/overview`, `POST /projects`, `GET /projects/{id}/export` | `dashboard.py`, `projects.py` | `dashboard_service`, `project_service`, `export_service` |
| `/dashboard/preferences` | `GET/PATCH /profile/preferences`, `GET /profile/style-templates`, `POST /profile/style-templates/{key}/apply`, `DELETE /profile/style-templates/active` | `profile.py` | `preference_service` |
| `/dashboard/projects/[projectId]/story-room` | Story Engine workspace, import templates, bulk import, outline stress test, realtime guard, chapter stream, final optimize, cloud drafts, project task playback, knowledge CRUD, search, project structure, chapter list/create/patch | `story_engine.py`, `tasks.py`, `projects.py`, `chapters.py` | `story_engine_workflow_service`, `story_engine_cloud_draft_service`, `task_service`, `story_engine_kb_service`, `project_service`, `chapter_service` |
| `/dashboard/projects/[projectId]/chapters` | `GET /projects/{id}/structure`, `GET /projects/{id}/chapters`, `POST /projects/{id}/chapters`, volume and branch create/update routes, project export | `projects.py`, `chapters.py` | `project_service`, `chapter_service`, `export_service` |
| `/dashboard/projects/[projectId]/bible` | `GET/PUT /projects/{id}/bible`, `GET /projects/{id}/canon-snapshot`, `GET /projects/{id}/bible/versions`, `GET /projects/{id}/bible/pending-changes`, branch item upsert/remove | `projects.py` | `project_service`, `story_bible_version_service`, `canon.service` |
| `/dashboard/projects/[projectId]/quality` | `GET /dashboard/projects/{id}/quality-trend` | `dashboard.py` | `dashboard_service` |
| `/dashboard/projects/[projectId]/collaborators` | collaborator list/create/update/delete | `projects.py` | `project_service` |
| `/dashboard/editor/[chapterId]` | chapter detail, versions, tasks, review workspace, chapter patch, generate, evaluate, rollback, rewrite selection, comments, reviews, checkpoints, export | `chapters.py`, `evaluation.py`, `tasks.py`, `/ws/tasks/{task_id}` | `chapter_service`, `review_service`, `rewrite_service`, `generation_service`, `task_service` |
| generation pages | generation endpoints plus Story Bible save | `projects.py` | `entity_generation_service`, Story Bible item routes |

## 3. Core Contracts by Area

### Dashboard

Frontend:
- `frontend/app/dashboard/page.tsx`

Backend:
- `GET /api/v1/dashboard/overview`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}/export`

Meaning:
- dashboard is a summary aggregator, not a raw project list page
- project creation is minimal and relies on backend default structure creation
- `GET /api/v1/dashboard/overview` 现在除了基础总量，还会返回 `activity_snapshot / quality_snapshot / task_health / pipeline_snapshot / genre_distribution / focus_queue`
- dashboard 前端已经开始把“当前最该处理什么”作为主视图之一，而不只是平铺项目列表
- dashboard 里的“最近发生了什么”目前主要消费 `overview.recent_tasks`，用于快速定位哪本书刚跑完、还在处理中，或者卡在了哪一步

### Preferences

Frontend:
- `frontend/app/dashboard/preferences/page.tsx`

Backend:
- `GET /api/v1/profile/preferences`
- `PATCH /api/v1/profile/preferences`
- `GET /api/v1/profile/style-templates`
- `POST /api/v1/profile/style-templates/{template_key}/apply`
- `DELETE /api/v1/profile/style-templates/active`

Meaning:
- profile preferences are both explicit settings and a view over learned style signals
- style templates are separate from learning snapshots
- `/dashboard/preferences` 现在是独立风格中心，不再只是跳转占位页
- 页面会把长期写法、底稿模板和一段本地保存的风格样文放在同一处收口
- 该页面支持通过 `projectId` 查询参数回跳到当前 `story-room`

### Project Structure and Chapters Workspace

Frontend:
- `frontend/app/dashboard/projects/[projectId]/chapters/page.tsx`

Backend:
- `GET /api/v1/projects/{project_id}/structure`
- `GET /api/v1/projects/{project_id}/chapters?branch_id=...&volume_id=...`
- `POST /api/v1/projects/{project_id}/chapters`
- `POST /api/v1/projects/{project_id}/volumes`
- `PATCH /api/v1/projects/{project_id}/volumes/{volume_id}`
- `POST /api/v1/projects/{project_id}/branches`
- `PATCH /api/v1/projects/{project_id}/branches/{branch_id}`

Meaning:
- chapter creation is branch-aware and volume-aware
- project structure is part of the content workflow, not just settings

### Story Room Workspace

Frontend:
- `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`

Backend:
- `GET /api/v1/projects/{project_id}/story-engine/workspace`
- `GET /api/v1/projects/{project_id}/story-engine/import-templates`
- `POST /api/v1/projects/{project_id}/story-engine/imports/bulk`
- `POST /api/v1/projects/{project_id}/story-engine/workflows/outline-stress-test`
- `POST /api/v1/projects/{project_id}/story-engine/workflows/realtime-guard`
- `POST /api/v1/projects/{project_id}/story-engine/workflows/chapter-stream`
- `POST /api/v1/projects/{project_id}/story-engine/workflows/final-optimize`
- `GET /api/v1/projects/{project_id}/story-engine/search`
- `GET /api/v1/projects/{project_id}/story-engine/cloud-drafts`
- `GET /api/v1/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}`
- `PUT /api/v1/projects/{project_id}/story-engine/cloud-drafts/current`
- `DELETE /api/v1/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}`
- `GET /api/v1/projects/{project_id}/task-playback`
- Story Engine entity CRUD routes
- `GET /api/v1/projects/{project_id}/structure`
- `GET /api/v1/projects/{project_id}/chapters`
- `POST /api/v1/projects/{project_id}/chapters`
- `PATCH /api/v1/chapters/{chapter_id}`

Meaning:
- `story-room` 已经是写手前台的真实主入口
- 它一边消费 Story Engine 工作流，一边把正文落入正式 `Chapter` 主链
- 它现在只暴露写手必要信息，完整 review/comment/checkpoint 仍保留在独立章节编辑器
- workspace 返回里已经补入 `knowledge_provenance`，后台可以按实体维度给出来源章节、关联设定和最近变更摘要，前台暂时仍保持黑盒
- `outline-stress-test` 现在也会返回 `workflow_timeline`，并持久化到统一任务系统，开书阶段不再是一次性黑盒调用
- `imports/bulk` 现在也会返回 `workflow_timeline`，并持久化到统一任务系统；模板导入、自定义设定包导入和覆盖区块替换都能进入最近过程回放
- `realtime-guard` 与 `final-optimize` 现在都会返回 `workflow_timeline`
- `chapter-stream` 的每条 NDJSON 事件现在都会带 `workflow_event`，终止事件会补齐完整 `workflow_timeline`
- `story-room` 现在同时消费“本机保稿 + 云端续写草稿”两层写作保护；正式章节保存、回滚、片段改写后，前台会主动清理当前章的云端续写稿
- `story-room` 现在还会把“当前页工作流时间线 + 项目任务回放”合并展示为写手可读的最近过程；`chapter-stream / realtime-guard / final-optimize` 也都已经正式并入统一任务系统
- Dashboard 和 `story-room` 的“最近过程”现在都能覆盖开书的大纲压力测试与初始化导入动作，不再只偏向正文阶段
- 这三条章节工作流现在都会额外接受可选 `chapter_id`，已落库章节会直接挂到真实章节任务链；未落库章节则退回项目级任务记录

### Story Bible Workspace

Frontend:
- `frontend/app/dashboard/projects/[projectId]/bible/page.tsx`

Backend:
- `GET /api/v1/projects/{project_id}/structure`
- `GET /api/v1/projects/{project_id}/bible?branch_id=...`
- `PUT /api/v1/projects/{project_id}/bible?branch_id=...`
- `POST /api/v1/projects/{project_id}/bible/item?branch_id=...`
- `POST /api/v1/projects/{project_id}/bible/item/remove?branch_id=...`
- `GET /api/v1/projects/{project_id}/canon-snapshot?branch_id=...`
- `GET /api/v1/projects/{project_id}/bible/versions?branch_id=...`
- `GET /api/v1/projects/{project_id}/bible/pending-changes?branch_id=...`
- `POST /api/v1/projects/{project_id}/bible/pending-changes`
- `POST /api/v1/projects/{project_id}/bible/pending-changes/{change_id}/approve`
- `POST /api/v1/projects/{project_id}/bible/pending-changes/{change_id}/reject`
- `POST /api/v1/projects/{project_id}/bible/check-conflict`

Meaning:
- project-level Bible editing and branch-level entity override editing are separate contracts
- the Bible page is the closest thing this project has to a canon control panel

Important payload distinction:

- full replace uses `StoryBibleUpdate`
- branch entity patch uses `StoryBibleBranchItemUpsert`
- branch entity delete uses `StoryBibleBranchItemDelete`

Correct branch item upsert shape:

```json
{
  "section_key": "characters",
  "item": {
    "name": "Example",
    "data": {},
    "version": 1
  }
}
```

Story knowledge mutation responses now also include:

- `entity_locator`

Meaning:

- 保存 / 删除设定后，后台会返回稳定锚点（`section_key / entity_id / entity_key / label / branch_id`）
- 这为后续“设定卡片定位”“正文与设定双向回跳”提供了统一坐标

Primary sources:
- `backend/schemas/project.py`
- `backend/services/project_service.py`

### Chapter Editor Workspace

Frontend:
- `frontend/app/dashboard/editor/[chapterId]/page.tsx`
- `frontend/components/editor/use-task-websocket.ts`

Backend:
- `GET /api/v1/chapters/{chapter_id}`
- `PATCH /api/v1/chapters/{chapter_id}`
- `GET /api/v1/chapters/{chapter_id}/versions`
- `GET /api/v1/chapters/{chapter_id}/review-workspace`
- `GET /api/v1/chapters/{chapter_id}/tasks`
- `POST /api/v1/chapters/{chapter_id}/generate`
- `POST /api/v1/chapters/{chapter_id}/evaluate`
- `POST /api/v1/chapters/{chapter_id}/rollback/{version_id}`
- `POST /api/v1/chapters/{chapter_id}/rewrite-selection`
- `POST /api/v1/chapters/{chapter_id}/comments`
- `PATCH /api/v1/chapters/{chapter_id}/comments/{comment_id}`
- `DELETE /api/v1/chapters/{chapter_id}/comments/{comment_id}`
- `POST /api/v1/chapters/{chapter_id}/reviews`
- `POST /api/v1/chapters/{chapter_id}/checkpoints`
- `PATCH /api/v1/chapters/{chapter_id}/checkpoints/{checkpoint_id}`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/events`
- `WS /ws/tasks/{task_id}`

Meaning:
- the editor is a compound workspace that joins chapter state, version history, live task state, and review state
- WebSocket updates are incremental, but the page still reloads authoritative state after task completion

### Quality View

Frontend:
- `frontend/app/dashboard/projects/[projectId]/quality/page.tsx`

Backend:
- `GET /api/v1/dashboard/projects/{project_id}/quality-trend?chapter_limit=...`

Meaning:
- project quality is modeled as a trend window, not a single current score

## 4. Known Contract Gaps

### Gap 1: Public Story Bible section semantics are aligned, and storage has entered native-first mode

Examples:
- items page now saves into native `items`
- factions page now saves into native `factions`
- Bible full replace and branch item patch/delete also expose `items` / `factions` as first-class public sections
- backend runtime now prefers native `project_items / project_factions` and canonical branch payloads
- legacy `world_settings` wrapper rows are only kept as历史兼容读取/自动迁移来源，不再是主存储语义

Primary sources:
- `frontend/app/dashboard/projects/[projectId]/bible/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/generations/items/page.tsx`
- `frontend/app/dashboard/projects/[projectId]/generations/factions/page.tsx`
- `backend/schemas/project.py`
- `backend/services/project_service.py`

Meaning:
- the frontend/backend contract is now semantically aligned
- the remaining debt is no longer “存储是不是原生”，而是后续 Story Bible 溯源、引用关系和更细粒度观测

### Gap 2: Entity generation has entered the project task/event chain

Routes like:
- `/generations/characters`
- `/generations/items`
- `/generations/locations`
- `/generations/factions`
- `/generations/plot-threads`

now route through `entity_generation_service`, which:
- prefers remote model generation through project-level model routing
- falls back to local heuristic generation when no provider is available or output is invalid
- records task state, task events, failover traces and candidate previews for the dispatch path

Meaning:
- these pages are no longer static scaffolds
- the writer-facing main path now uses dispatch + task/event updates instead of only synchronous request/response

Primary sources:
- `backend/api/v1/projects.py`
- `backend/services/entity_generation_service.py`
- `backend/tasks/entity_generation.py`

### Gap 3: story-room 已接入正式章节主链，但没有承载完整审校面板

当前状态：

- `story-room` 已能读取真实章节列表
- 已能创建和更新正式 `Chapter`
- 已能展示基础版本号、状态和 final gate 信息
- 但 comment / checkpoint / review decision / rollback / rewrite selection 等深度审校操作，仍然集中在 `/dashboard/editor/[chapterId]`

Meaning:
- 写手主工作台已经可用
- 但如果要把旧章节编辑器完全退到后台，还需要继续把深度审校能力按产品节奏迁入 `story-room`

Primary sources:
- `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`
- `frontend/app/dashboard/editor/[chapterId]/page.tsx`
- `backend/api/v1/chapters.py`

## 5. Practical Reading of the API Surface

The API surface is already rich enough to show the real product direction:

- dashboard aggregation
- style learning and templates
- structured project branch/volume management
- Story Bible branch overrides and canon inspection
- versioned chapter editing
- live generation tasks
- review and checkpoint workflow

The main remaining gaps are not in the chapter workflow.
They are mostly in Story Bible storage/domain purity, entity-generation orchestration depth, and environment consistency around backend development.
