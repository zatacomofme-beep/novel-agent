# 项目文件结构

```
novels/
├── README.md                  # 项目说明文档
├── PRD.md                     # 产品需求文档
├── .gitignore                 # Git 忽略文件
├── docker-compose.yml         # Docker Compose 配置
│
├── frontend/                  # Next.js 前端应用
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── .env.example
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/
│   │   │   ├── page.tsx        # 仪表板
│   │   │   ├── projects/
│   │   │   ├── editor/
│   │   │   └── settings/
│   │   └── api/                # BFF 层
│   ├── components/
│   │   ├── ui/                 # 基础 UI 组件
│   │   ├── editor/             # 编辑器组件
│   │   ├── agent/              # Agent 相关组件
│   │   └── visualization/      # 可视化组件
│   ├── hooks/
│   ├── stores/                 # Zustand 状态管理
│   ├── lib/
│   └── types/
│
├── backend/                   # FastAPI 后端服务
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── chapters.py
│   │   │   ├── agents.py
│   │   │   └── evaluation.py
│   │   └── deps.py
│   │
│   ├── agents/                # Agent 核心实现
│   │   ├── base.py            # Agent 基类
│   │   ├── architect.py       # 架构师 Agent
│   │   ├── writer.py          # 撰稿人 Agent
│   │   ├── critic.py          # 批判家 Agent
│   │   ├── editor.py          # 编辑 Agent
│   │   ├── emotion_designer.py # 情感设计师 Agent
│   │   ├── librarian.py       # 资料员 Agent
│   │   ├── coordinator.py     # 协调器
│   │   └── debate.py          # 辩论系统
│   │
│   ├── bus/                   # 消息总线
│   │   ├── protocol.py
│   │   ├── message_bus.py
│   │   └── events.py
│   │
│   ├── memory/                # 记忆系统
│   │   ├── story_bible.py
│   │   ├── vector_store.py
│   │   ├── state.py
│   │   └── version_control.py
│   │
│   ├── evaluation/            # 质量评估
│   │   ├── metrics.py
│   │   ├── evaluator.py
│   │   ├── ai_detection.py
│   │   └── consistency.py
│   │
│   ├── models/                # 数据模型
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── character.py
│   │   ├── chapter.py
│   │   └── evaluation.py
│   │
│   ├── db/                    # 数据库
│   │   ├── session.py
│   │   ├── repository.py
│   │   └── migrations/
│   │
│   ├── tasks/                 # Celery 任务
│   │   ├── celery_app.py
│   │   ├── chapter_generation.py
│   │   └── evaluation.py
│   │
│   └── core/                  # 核心配置
│       ├── config.py
│       ├── security.py
│       └── logging.py
│
└── infrastructure/            # 基础设施配置
    └── docker/
        ├── Dockerfile.backend
        ├── Dockerfile.frontend
        ├── docker-compose.yml
        ├── nginx/
        └── scripts/
```

## 核心目录说明

### `/frontend`
Next.js 14 前端应用，使用 App Router 架构。
- `app/`: 页面和路由
- `components/`: React 组件
- `hooks/`: 自定义 Hooks
- `stores/`: Zustand 状态管理
- `lib/`: 工具函数和配置

### `/backend/agents`
多 Agent 系统核心实现。
- `base.py`: Agent 基类和接口定义
- `architect.py`: 架构师 Agent（整体规划）
- `writer.py`: 撰稿人 Agent（具体写作）
- `critic.py`: 批判家 Agent（质量审核）
- `editor.py`: 编辑 Agent（润色优化）
- `emotion_designer.py`: 情感设计师 Agent
- `librarian.py`: 资料员 Agent（记忆管理）
- `coordinator.py`: 协调器（任务调度）
- `debate.py`: 辩论系统

### `/backend/memory`
记忆系统，实现长期一致性。
- `story_bible.py`: 故事圣经（设定管理）
- `vector_store.py`: 向量数据库（RAG 检索）
- `state.py`: 状态管理
- `version_control.py`: 版本控制

### `/backend/evaluation`
质量评估体系。
- `metrics.py`: 14 维度评估指标
- `evaluator.py`: 评估器实现
- `ai_detection.py`: AI 味检测
- `consistency.py`: 一致性检查

### `/backend/bus`
消息总线，Agent 间通信。
- `protocol.py`: 通信协议定义
- `message_bus.py`: 消息总线实现
- `events.py`: 事件定义

### `/backend/models`
Pydantic 数据模型。
- `user.py`: 用户模型
- `project.py`: 项目模型
- `character.py`: 人物模型
- `chapter.py`: 章节模型
- `evaluation.py`: 评估模型

### `/backend/db`
数据库相关。
- `session.py`: 数据库会话
- `repository.py`: 数据访问层
- `migrations/`: 数据库迁移

### `/backend/tasks`
Celery 异步任务。
- `celery_app.py`: Celery 配置
- `chapter_generation.py`: 章节生成任务
- `evaluation.py`: 评估任务

### `/infrastructure/docker`
Docker 配置。
- `Dockerfile.backend`: 后端 Docker 镜像
- `Dockerfile.frontend`: 前端 Docker 镜像
- `docker-compose.yml`: 服务编排
- `nginx/`: Nginx 配置
- `scripts/`: 部署脚本
