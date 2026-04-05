# 开发说明

这份文档只描述当前真实可用的开发方式，不再沿用旧工作流页面和旧环境假设。

## 先建立统一认知

当前项目有三条最重要的事实：

1. 写手前台主入口已经收口到 `story-room`
2. `story-room` 里的正文现在会写入正式 `Chapter` 主链，而不是只停留在本地状态
3. 模型路由属于后台管理员 / 系统配置层，不属于写手前台功能

## 环境矩阵

| 场景 | 后端环境文件 | 前端环境文件 | 说明 |
| --- | --- | --- | --- |
| 本机直跑 | `backend/.env` | `frontend/.env` | 适合直接调试 Python / Next |
| Docker Compose | `backend/.env.compose` | `frontend/.env.compose` | 适合一键启动整套服务 |
| 参考模板 | `backend/.env.example` / `backend/.env.compose.example` | `frontend/.env.example` | 示例文件不要直接存密钥 |

注意：

- `backend/.env.example` 面向本机直跑，默认走 `localhost`
- `backend/.env.compose.example` 面向容器内运行，默认走 `postgres / redis / qdrant`
- 不要把真实 API Key 提交进仓库
- 不要把模型配置暴露到写手前台

## Docker Compose 开发

### 1. 准备环境文件

```bash
cp backend/.env.compose.example backend/.env.compose
```

如果前端需要自定义地址，再额外创建：

```bash
cp frontend/.env.example frontend/.env.compose
```

### 2. 启动服务

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

### 3. 常用命令

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f celery_worker
docker compose logs -f frontend
docker compose down
```

### 4. Compose 配置验证

```bash
docker compose config
docker compose -f infrastructure/docker/docker-compose.prod.yml config
```

## 本机直跑开发

### 1. 准备环境文件

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. 后端

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Celery Worker

```bash
cd backend
source venv/bin/activate
celery -A tasks.celery_app worker --loglevel=info --pool=solo
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev
```

## 生产部署

生产 Compose 入口：

```bash
cp backend/.env.compose.example backend/.env.compose
docker compose -f infrastructure/docker/docker-compose.prod.yml up -d --build
```

当前生产编排已经补齐这些组件：

- PostgreSQL
- Redis
- Qdrant
- FastAPI
- Celery Worker
- Next.js
- Nginx

## 关键开发入口

### 写手工作台

- [story-room/page.tsx](./frontend/app/dashboard/projects/[projectId]/story-room/page.tsx)
- [draft-studio.tsx](./frontend/components/story-engine/draft-studio.tsx)
- [knowledge-base-board.tsx](./frontend/components/story-engine/knowledge-base-board.tsx)

### 正式章节主链

- [router.py](./backend/api/v1/router.py)
- [chapters.py](./backend/api/v1/chapters.py)
- [chapter_service.py](./backend/services/chapter_service.py)
- [review_service.py](./backend/services/review_service.py)
- [chapter-lifecycle.md](./docs/architecture/chapter-lifecycle.md)

### Story Engine 工作流与知识库

- [story_engine.py](./backend/api/v1/story_engine.py)
- [story_engine_kb_service.py](./backend/services/story_engine_kb_service.py)
- [story_engine_workflow_service.py](./backend/services/story_engine_workflow_service.py)
- [story_engine.py](./backend/models/story_engine.py)

### 后台模型路由

- [story_engine_settings_service.py](./backend/services/story_engine_settings_service.py)
- [story_engine_model_profiles.json](./backend/config/story_engine_model_profiles.json)
- [story-engine-models.md](./docs/setup/story-engine-models.md)

## 验证命令

### 前端

```bash
cd frontend
npm run type-check
```

### 一键关键检查

从仓库根目录直接执行：

```bash
bash scripts/run_delivery_checks.sh
```

如果你要连模型网关一起验证：

```bash
RUN_MODEL_VERIFY=1 bash scripts/run_delivery_checks.sh
```

### 后端语法与测试

```bash
cd backend
./venv/bin/python -m py_compile api/main.py api/v1/router.py
PYTHONPATH=. ./venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

### Story Engine 模型连通性

```bash
cd backend
PYTHONPATH=. ./venv/bin/python scripts/verify_story_engine_models.py
```

### Story Engine 端到端烟雾测试

```bash
cd backend
PYTHONPATH=. STORY_ENGINE_SMOKE_BASE_URL=http://127.0.0.1:8000/api/v1 ./venv/bin/python scripts/story_engine_live_smoke.py
```

### story-room 前端冒烟

如果你改了首页、登录、Dashboard 或 `story-room` 主链，建议额外执行：

```bash
bash scripts/run_story_room_e2e.sh
```

这条脚本会：

- 检查本机 PostgreSQL 是否可用
- 启动本地后端
- 运行 `frontend/tests/e2e/story-room-smoke.spec.ts`

## 当前开发约束

### 写手前台

- 不暴露 Agent、模型、路由策略等技术术语
- 统一以“测大纲漏洞”“查人设 bug”“优化爽点”“自动记设定”这类文案呈现
- `story-room` 是优先维护对象，旧页面更多承担兼容与补充职责

### 后台模型配置

- 当前没有写手可见的模型配置页
- 模型预设与角色路由由后端配置文件和 API 承担
- 真正的配置入口是项目级 `story_engine_settings` 和全局 `story_engine_model_profiles.json`

### 章节真相源

- 编辑区文本必须优先落入 `Chapter`
- 章节发布判断以 `final_gate_status` 为准，不以 `status=final` 单独作为真相
- 内容变更会触发版本递增和部分 gate stale，这是预期行为，不要绕开

## 常见排查

### 1. Docker 里模型请求总是没走真实 Key

优先检查：

- 是否创建了 `backend/.env.compose`
- `docker compose config` 里是否出现你期望的模型字段
- 是否误把密钥只写进了 `backend/.env`
- 如果本机要直接 `source backend/.env.example`，记得先同步仓库里的最新版示例文件

### 2. Story Engine 在容器里检索不到知识库

优先检查：

- `qdrant` 服务是否正常启动
- 容器内使用的 `QDRANT_URL` 是否指向 `http://qdrant:6333`
- 是否只是退回到了词法 / 内存兜底检索

### 3. `story-room` 保存了正文，但状态看起来不对

优先检查：

- 当前章节是否已经创建为正式 `Chapter`
- 这次保存是否触发了新版本
- `final_gate_status` 是否因为评估 stale / review / checkpoint 被阻塞

## 推荐阅读顺序

1. [README.md](./README.md)
2. [docs/HANDOFF.md](./docs/HANDOFF.md)
3. [docs/architecture/README.md](./docs/architecture/README.md)
4. [docs/architecture/chapter-lifecycle.md](./docs/architecture/chapter-lifecycle.md)
5. [docs/architecture/api-contract-map.md](./docs/architecture/api-contract-map.md)
6. [docs/setup/story-engine-models.md](./docs/setup/story-engine-models.md)
