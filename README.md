# 长篇小说创作 Agent

> 面向严肃创作者的深度 AI 协作系统 - 用时间换质量，打造无 AI 味的精品内容

## 🎯 产品定位

帮助想要写出"没有 AI 味道"小说的创作者，通过多 Agent 协作、反思循环、质量评估等技术，打造可出版的精品长篇小说。

**核心价值**：
- ✅ **无 AI 味** - AI 检测通过率 >90%
- ✅ **严谨** - 百万字不崩坏，一致性评分 >0.85
- ✅ **可控** - 用户是创意总监，AI 是执行团队

## 🚀 快速开始

### 前置要求

- Node.js 18+
- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 15+
- Qdrant 1.8+

### 环境配置

1. 克隆项目
```bash
git clone <repository-url>
cd novels
```

2. 配置环境变量
```bash
# 后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置数据库和模型 API 密钥

# 前端环境变量
cp frontend/.env.example frontend/.env
```

3. 启动服务
```bash
# 使用 Docker Compose 启动所有服务
docker-compose up -d

# 或分别启动
# 启动数据库
docker-compose up -d postgres qdrant redis

# 启动后端
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload

# 启动前端
cd frontend
npm install
npm run dev
```

4. 无基础设施验证
```bash
# 后端单测与迁移链验证
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. \
APP_NAME='Long Novel Agent' \
APP_ENV=development \
APP_DEBUG=true \
API_V1_PREFIX=/api/v1 \
DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/novel_agent' \
REDIS_URL='redis://localhost:6379/0' \
CELERY_BROKER_URL='redis://localhost:6379/1' \
CELERY_RESULT_BACKEND='redis://localhost:6379/2' \
QDRANT_URL='http://localhost:6333' \
JWT_SECRET_KEY='replace-me' \
python -m unittest discover -s tests -p 'test_*.py' -v
alembic -c alembic.ini upgrade head --sql > /tmp/novels-alembic.sql

# 前端静态验证
cd ../frontend
npm install
npm run type-check
```

5. 访问应用
- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 📁 项目结构

```
novels/
├── frontend/              # Next.js 前端应用
│   ├── app/              # App Router 页面
│   ├── components/       # React 组件
│   ├── hooks/            # 自定义 Hooks
│   ├── stores/           # Zustand 状态管理
│   └── lib/              # 工具函数
│
├── backend/              # FastAPI 后端服务
│   ├── api/              # API 路由
│   ├── agents/           # Agent 核心实现
│   │   ├── base.py       # Agent 基类
│   │   ├── architect.py  # 架构师 Agent
│   │   ├── writer.py     # 撰稿人 Agent
│   │   ├── critic.py     # 批判家 Agent
│   │   ├── editor.py     # 编辑 Agent
│   │   └── coordinator.py # 协调器
│   │
│   ├── bus/              # 消息总线
│   ├── memory/           # 记忆系统
│   ├── evaluation/       # 质量评估
│   ├── models/           # 数据模型
│   ├── db/               # 数据库
│   └── tasks/            # Celery 任务
│
├── infrastructure/       # 基础设施配置
│   └── docker/           # Docker 配置文件
│
├── docker-compose.yml    # Docker Compose 配置
└── PRD.md               # 产品需求文档
```

## 🏗️ 技术架构

### 前端
- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript 5.x
- **UI**: shadcn/ui + Tailwind CSS
- **状态**: Zustand + React Query
- **图表**: Recharts
- **编辑器**: TipTap / Monaco Editor

### 后端
- **框架**: FastAPI
- **语言**: Python 3.9+
- **数据库**: PostgreSQL 15+
- **向量库**: Qdrant
- **缓存**: Redis
- **任务队列**: Celery

### AI 架构
- **多 Agent 系统**: 架构师、撰稿人、批判家、编辑、情感设计师、资料员
- **RAG**: 检索增强生成
- **反思循环**: 多轮评估与改进
- **质量评估**: 14 维度评估体系

## 📖 核心功能

### 1. 故事圣经（Story Bible）
结构化管理所有设定，支持版本控制和自动更新。
- 人物档案
- 世界观设定
- 大纲管理
- 伏笔追踪

### 2. 多 Agent 创作
- **架构师**: 整体规划、终审
- **撰稿人**: 具体写作
- **批判家**: 质量审核（一致性、AI 味）
- **编辑**: 润色优化
- **情感设计师**: 情感曲线设计
- **资料员**: RAG 检索

### 3. 质量评估体系
14 维度评估：
- 基础质量（流畅度、词汇丰富度、句式变化）
- 叙事质量（情节紧凑度、冲突强度、悬念）
- 一致性质量（人物、世界观、逻辑、时间线）
- 艺术质量（情感共鸣、意象、对话、主题）
- AI 味检测

### 4. 反思循环
```
生成初稿 → 多轮评估 → 问题识别 → Agent 辩论 → 修改优化 → 最终审核
```

## 📊 开发路线图

### Phase 1: MVP（第 1-12 周）
- ✅ 项目初始化
- ✅ 基础功能（用户、项目、设定）
- 🔄 多 Agent 系统
- 📋 质量评估体系
- 🎯 **目标**: 能生成 3000 字章节，一致性>0.7，AI 味<0.4

### Phase 2: V1.0（第 13-24 周）
- 情感设计师 Agent
- 编辑 Agent（去 AI 味）
- 反思循环引擎
- 可视化（质量雷达图、人物关系图）
- **目标**: 能生成 10 万字，AI 味<0.3

### Phase 3: V2.0（第 25-52 周）
- 学习系统（用户偏好）
- 风格模型微调
- 多卷本规划
- 协作编辑
- **目标**: 能生成 100 万字+，AI 味<0.2

## 💰 商业模式

| 版本 | 价格 | 功能 |
|------|------|------|
| **免费** | ¥0 | 基础生成，每月 2 万字 |
| **专业版** | ¥99/月 | 50 万字 + 质量评估 + 情感曲线 |
| **工作室版** | ¥299/月 | 无限字 + 多项目 + 风格定制 |
| **企业版** | 定制 | 私有部署 + 专属模型 |

## 🤝 参与贡献

我们欢迎各种形式的贡献！

### 开发环境设置
```bash
# 克隆项目
git clone <repository-url>
cd novels

# 启动开发环境
docker-compose up -d

# 安装依赖
cd frontend && npm install
cd ../backend && pip install -r requirements.txt
```

### 提交 PR
1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

MIT License

## 📞 联系方式

- 产品问题：查看 [PRD.md](./PRD.md)
- 技术问题：查看项目 Wiki
- Bug 反馈：提交 Issue

## 🙏 致谢

感谢所有贡献者和用户！

---

**状态**: 开发中 🚧

**当前版本**: v0.1.0 (MVP 开发中)

**最后更新**: 2026-03-18
