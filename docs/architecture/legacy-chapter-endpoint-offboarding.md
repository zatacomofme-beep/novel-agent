# Legacy Chapter Endpoints Offboarding

这份文档用于推进 `backend/api/v1/chapters.py` 里历史兼容入口的下线。
目标不是一次性删除，而是按“可观测 -> 迁移 -> 下线”分批推进，避免打断真实调用方。

## 1. 当前状态

- 前端主路径（`story-room` 与 editor 相关 helper）已经切到 project-scoped 路由：
  - `/api/v1/projects/{project_id}/story-engine/chapters/*`
- Playwright E2E 已切换到主链路由，不再使用 `/api/v1/chapters/*` 做章节 patch seed。
- 后端新增了 legacy 入口观测日志事件：
  - `legacy_chapter_endpoint_used`
  - 字段：`endpoint_name`, `chapter_id`, `user_id`
- 软下线响应头已启用（统一中间件）：
  - `Deprecation: true`
  - `Sunset: Wed, 31 Dec 2026 23:59:59 GMT`
- 已提供可切换硬拦截开关：
  - 环境变量 `LEGACY_CHAPTER_ROUTES_MODE`
  - `compat`（默认）: 继续兼容并返回软下线头
  - `gone`: `/api/v1/chapters/*` 统一返回 `410 Gone`

## 2. 兼容入口分组

### Group A: 已完成硬删除（2026-04-05）

以下旧入口已从 `backend/api/v1/chapters.py` 移除：

- `GET /api/v1/chapters/{chapter_id}`
- `PATCH /api/v1/chapters/{chapter_id}`
- `GET /api/v1/chapters/{chapter_id}/versions`
- `GET /api/v1/chapters/{chapter_id}/review-workspace`
- `POST /api/v1/chapters/{chapter_id}/comments`
- `PATCH /api/v1/chapters/{chapter_id}/comments/{comment_id}`
- `DELETE /api/v1/chapters/{chapter_id}/comments/{comment_id}`
- `POST /api/v1/chapters/{chapter_id}/reviews`
- `POST /api/v1/chapters/{chapter_id}/checkpoints`
- `PATCH /api/v1/chapters/{chapter_id}/checkpoints/{checkpoint_id}`
- `POST /api/v1/chapters/{chapter_id}/rewrite-selection`
- `POST /api/v1/chapters/{chapter_id}/rollback/{version_id}`
- `GET /api/v1/chapters/{chapter_id}/export`

说明：

- 这批能力已经完全收口到 project-scoped `story-engine/chapters/*` 主链。
- 旧路径仍会在中间件层收到 `Deprecation/Sunset`（compat）或 `410`（gone）信号。

### Group B: 仍是 legacy 语义（后续改造后再下线）

这些接口仍承担历史入口职责，需要先迁移语义：

- `POST /api/v1/chapters/{chapter_id}/generate`
  - 当前是 legacy generation dispatch 入口
- `POST /api/v1/chapters/{chapter_id}/beta-reader`
  - 当前是 legacy sidecar analysis 入口

### Group C: 邻接的非 `chapters.py` 旧风格接口（单独治理）

不在 `chapters.py`，但仍使用 chapter-id 直连语义，建议并行列入迁移清单：

- `GET /api/v1/chapters/{chapter_id}/tasks` (`backend/api/v1/tasks.py`)
- `POST /api/v1/chapters/{chapter_id}/evaluate` (`backend/api/v1/evaluation.py`)

当前进度：

- 已补 project-scoped 等价入口：
  - `GET /api/v1/projects/{project_id}/story-engine/chapters/{chapter_id}/tasks`
  - `POST /api/v1/projects/{project_id}/story-engine/chapters/{chapter_id}/evaluate`
- 原 chapter-id 入口仍保留兼容，并带 `legacy_chapter_endpoint_used` 观测日志。

## 3. 下线节奏建议

1. 观测窗口（建议 7-14 天）
- 统计 `legacy_chapter_endpoint_used` 的调用量与调用来源（用户行为、脚本、自动化）。
- 重点关注 Group B（`generate` / `beta-reader`）和 Group C（`tasks` / `evaluate`）。

2. 软下线（建议 3-7 天）
- 对剩余 legacy 入口持续返回响应头告警（`Deprecation` / `Sunset`）。
- 同步对外通知（若有外部集成方）。

3. 硬下线（后续批次）
- 批次 2：在 workflow 完整迁移后删除 Group B 与 Group C。

## 4. 回归守卫

- 已有守卫：前端不得重新引入 `/api/v1/chapters/*` 调用。
  - `backend/tests/test_frontend_chapter_api_contract_guard.py`
- 建议保留并持续执行：
  - `scripts/run_delivery_checks.sh`
  - `scripts/run_story_room_e2e.sh`
  - 后端全量 `unittest`
