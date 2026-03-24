# 网文创作平台

面向长篇网文创作的一体化写作系统。当前仓库的产品目标已经明确收口为一条主路径：

- AI 起稿与续写
- 多轮收敛优化
- 设定圣经自动沉淀
- 本章 100-300 字总结
- 前台极简，后台黑盒

- 写手前台主入口是 `story-room`
- 正式章节真相源是 `Chapter / ChapterVersion / Review / Final Gate`
- 动态设定真相源是 Story Engine 知识库与版本记录
- 模型路由是后台能力，不在写手前台暴露

## 当前产品形态

写手真正会使用的页面只保留：

- `/dashboard`
- `/dashboard/projects/[projectId]/story-room`

`story-room` 现在已经具备这几个核心闭环：

- 大纲工作台：发起大纲压力测试，生成并展示三级大纲
- 创作编辑器：流式起稿、实时设定守护、手动保存正式章节
- 正式章节主链：保存后进入 `Chapter` 主链，自动拥有版本号、状态与发布门信息
- 设定圣经：人物、伏笔、物品、地点、势力、剧情线、规则与时间线的统一维护
- 终稿优化：一键触发深度校验，展示原稿 vs 优化稿，并生成 100-300 字章节总结

前台有意隐藏这些技术细节：

- Agent
- 辩论
- 模型组合
- 向量检索

这些能力都仍然存在，但它们属于后台系统和管理员配置层。

## 技术栈

- 前端：Next.js 14 + TypeScript + Tailwind
- 后端：FastAPI + SQLAlchemy + Celery
- 主数据库：PostgreSQL
- 向量检索：Qdrant + Chroma
- 工作流 / 协作：LangGraph + 多角色模型路由
- 实时任务：Redis + WebSocket task events

## 快速开始

### 方式一：Docker Compose 开发环境

这是最快的启动方式，适合想直接把整套工作台跑起来。

1. 准备后端容器环境文件

```bash
cp backend/.env.compose.example backend/.env.compose
```

2. 按需填写 `backend/.env.compose`

至少建议补这些字段：

- `MODEL_GATEWAY_API_KEY`
- `MODEL_GATEWAY_BASE_URL`
- `OPENAI_API_KEY` 或其他兼容网关字段
- 各个 `STORY_ENGINE_*_MODEL`

3. 启动整套服务

```bash
docker compose up -d
```

4. 首次启动时执行迁移

```bash
docker compose exec backend alembic upgrade head
```

5. 访问服务

- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- Chroma：http://localhost:8001
- Qdrant：http://localhost:6333

生产 Compose 也沿用 `backend/.env.compose` 这套容器内配置语义。

### 方式二：本机直跑前后端

适合本机自己装了 PostgreSQL / Redis / Qdrant / Chroma，或者你要单独调试 Python / Next。

1. 准备环境文件

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

2. 安装依赖

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

3. 启动后端

```bash
cd backend
source venv/bin/activate
alembic upgrade head
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

4. 启动前端

```bash
cd frontend
npm run dev
```

## 环境文件说明

这一步很重要，仓库里现在明确分成两套环境文件语义：

| 文件 | 用途 |
| --- | --- |
| `backend/.env.example` | 本机直接运行后端 / worker 的参考模板 |
| `backend/.env.compose.example` | Docker Compose 容器内运行后端 / worker 的参考模板 |
| `backend/.env.compose` | 你自己的 Docker Compose 覆盖文件，不提交仓库 |
| `frontend/.env.example` | 前端本机 / Compose 开发默认值 |
| `frontend/.env.compose` | 前端 Compose 覆盖文件，不提交仓库 |

不要把真实密钥写进前端环境变量。

## 关键验证命令

### 前端类型检查

```bash
cd frontend
npm run type-check
```

### 后端模型路由校验

```bash
cd backend
PYTHONPATH=. python3 scripts/verify_story_engine_models.py
```

### Story Engine 联调烟雾测试

默认脚本会自己注册账号、创建项目、导入模板、执行实时守护、流式起稿和终稿优化。

```bash
cd backend
PYTHONPATH=. STORY_ENGINE_SMOKE_BASE_URL=http://127.0.0.1:8000/api/v1 python3 scripts/story_engine_live_smoke.py
```

## 当前目录重点

```text
novels/
├── frontend/
│   ├── app/dashboard/
│   │   ├── page.tsx
│   │   └── projects/[projectId]/story-room/page.tsx
│   ├── components/story-engine/
│   └── types/api.ts
├── backend/
│   ├── api/v1/
│   │   ├── projects.py
│   │   ├── chapters.py
│   │   ├── tasks.py
│   │   ├── evaluation.py
│   │   └── story_engine.py
│   ├── services/
│   │   ├── chapter_service.py
│   │   ├── review_service.py
│   │   ├── story_engine_kb_service.py
│   │   ├── story_engine_workflow_service.py
│   │   └── story_engine_settings_service.py
│   ├── config/story_engine_model_profiles.json
│   └── scripts/
├── docs/
│   ├── architecture/
│   └── setup/
├── docker-compose.yml
└── DEVELOPMENT.md
```

## 关键文档

- [DEVELOPMENT.md](./DEVELOPMENT.md)
- [架构索引](./docs/architecture/README.md)
- [章节生命周期](./docs/architecture/chapter-lifecycle.md)
- [前后端契约图](./docs/architecture/api-contract-map.md)
- [模型接入说明](./docs/setup/story-engine-models.md)

## 当前状态

这条主线已经基本明确：

- 模型路由已下沉到后台配置层
- `story-room` 已接入正式章节主链
- 文档与基础设施正在按新主产品形态收口

下一阶段更值得继续推进的，是：

- `items / factions` 的底层领域建模纯化
- 实体生成链是否并入 task / event / workflow 主链
- 管理端模型路由能力是否需要独立后台页面
