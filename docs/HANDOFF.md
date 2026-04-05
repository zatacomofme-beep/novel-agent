# 项目交接说明

这份文档面向“第一次接手这个仓库的人”。
目标不是重复架构细节，而是帮助你在最短时间内回答四个问题：

1. 这个项目现在主线是什么
2. 我应该先看哪些文件
3. 我本地怎么验证环境是正常的
4. 现在还有哪些已知的维护注意点

## 1. 当前主线

当前真实主线已经收口到：

- 前台主入口：`/dashboard`、`/dashboard/projects/[projectId]/story-room`
- 后台主入口：`backend/api/v1/story_engine.py`
- 编排中枢：`backend/services/story_engine_workflow_service.py`
- 正式章节真相层：`Chapter / ChapterVersion / Review / Checkpoint / Evaluation / Final Gate`
- 动态知识真相层：`StoryCharacter / StoryItem / StoryOutline / StoryChapterSummary / StoryKnowledgeVersion`

当前运行时向量检索已经统一到 Qdrant，不再依赖 Chroma。

## 2. 建议先读的文件

如果你只想快速建立正确认知，建议按这个顺序：

1. `README.md`
2. `DEVELOPMENT.md`
3. `docs/PROJECT_OVERVIEW.md`
4. `docs/architecture/README.md`
5. `docs/architecture/chapter-lifecycle.md`
6. `docs/architecture/api-contract-map.md`
7. `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`
8. `backend/api/v1/story_engine.py`
9. `backend/services/story_engine_workflow_service.py`
10. `backend/services/story_engine_kb_service.py`
11. `backend/services/chapter_service.py`
12. `backend/config/story_engine_model_profiles.json`

## 3. 本地环境基线

### 后端

- Python：`3.11`
- 推荐解释器：`backend/venv/bin/python`
- 安装命令：

```bash
python3.11 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements-dev.txt
```

### 前端

- Node：建议 `20.x`
- 安装命令：

```bash
cd frontend
npm ci
```

### 环境文件

- 本机直跑：`backend/.env` + `frontend/.env`
- Compose：`backend/.env.compose` + `frontend/.env.compose`

## 4. 最小验收流程

如果你改完代码，建议至少跑这一组：

```bash
bash scripts/run_delivery_checks.sh
```

它会做：

- 后端 Story Engine 关键测试
- 前端 TypeScript 检查

如果你要做更完整的本地验收，再补这组：

```bash
cd backend
PYTHONPATH=. ./venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q

cd ../frontend
npm run lint
npm run test
```

如果你改了首页、登录、Dashboard 或 `story-room` 主流程，建议再补：

```bash
bash scripts/run_story_room_e2e.sh
```

## 5. 当前自动化基线

仓库当前已经有基础 CI：

- `.github/workflows/ci.yml`

CI 会执行：

- 后端依赖安装
- 前端依赖安装
- `bash scripts/run_delivery_checks.sh`
- 后端全量 `unittest`
- 前端 `lint`
- 前端 `Vitest`
- `story-room` Playwright E2E 冒烟

## 6. 当前已知注意点

### 1. 前端单测不是空的了，但覆盖仍然偏工具层

当前 `Vitest` 已经覆盖：

- `api.ts`
- `auth.ts`
- `errors.ts`
- `quality-trend.tsx` 的纯函数
- `editor/formatters.ts`
- `story-bible-deeplink.ts`
- `story-bible-save.ts`
- `story-room-local-draft.ts`

但 `story-room` 页面主体本身仍然以集成行为为主，更多依赖 Playwright 和后端烟雾测试来兜住。

### 2. 后端全量测试已通过，但仍可能看到少量非阻塞日志

例如：

- `task_event_broker_redis_unavailable`
- 少量 `asyncio` 慢任务提示

这些在当前测试基线下不代表失败，只是某些失败路径/兜底路径被刻意覆盖。

### 3. 历史文档里仍保留少量“Chroma 已废弃”的迁移上下文

这类描述主要存在于路线图或历史分析文档中，代表的是“以前如何迁移”，不是“当前运行时仍在使用”。

## 7. 适合继续推进的方向

如果你接手后要继续做产品或工程推进，当前最顺的方向通常是：

1. 继续给 `story-room` 的关键状态流补单测/集成测
2. 把 Dashboard 和 `story-room` 的信息去重继续收口
3. 继续压缩历史兼容层，把真正不再使用的旁系页面/API 彻底归档
4. 把发布前检查和交付文档继续标准化
