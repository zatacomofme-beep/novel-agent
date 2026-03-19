# 长篇小说 Agent - 开发文档

## 开发环境设置

### 1. 前置要求

- **Node.js**: 18.x 或更高版本
- **Python**: 3.9.x 或更高版本
- **Docker**: 24.x 或更高版本
- **Docker Compose**: 2.x 或更高版本

### 2. 快速开始

#### 2.1 克隆项目

```bash
git clone <repository-url>
cd novels
```

#### 2.2 配置环境变量

**后端环境变量** (`backend/.env`):
```bash
# 数据库
DATABASE_URL=postgresql://postgres:password@localhost:5432/novel_agent
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333

# JWT 配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI 模型
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
DEFAULT_MODEL=claude-3-5-sonnet

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# 日志
LOG_LEVEL=DEBUG
```

**前端环境变量** (`frontend/.env`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

#### 2.3 使用 Docker 启动（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

#### 2.4 本地开发（不使用 Docker）

**启动数据库服务**（需要预先安装）:
```bash
# PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# 创建数据库
createdb novel_agent

# Qdrant
brew install qdrant
brew services start qdrant

# Redis
brew install redis
brew services start redis
```

**启动后端**:
```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端**:
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

#### 2.5 无基础设施验证链

如果当前机器没有安装 `Docker / PostgreSQL / Redis / Qdrant`，可以先跑下面这条最小验证链，确认仓库本身处于可开发状态：

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 运行单元测试
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

# 验证迁移链可生成离线 SQL
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
alembic -c alembic.ini upgrade head --sql > /tmp/novels-alembic.sql

# 前端
cd ../frontend
npm install
npm run type-check
```

**启动 Celery Worker**:
```bash
cd backend
source venv/bin/activate

# 启动 worker
celery -A tasks.celery_app worker --loglevel=info --pool=solo

# 启动 flower（监控）
celery -A tasks.celery_app flower --port=5555
```

### 3. 访问服务

启动后，访问以下地址：

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **Celery Flower**: http://localhost:5555

### 4. 数据库迁移

```bash
cd backend
source venv/bin/activate

# 创建新迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history
```

### 5. 运行测试

```bash
# 后端测试
cd backend
python -m unittest discover -s tests -p 'test_*.py' -v

# 前端静态验证
cd frontend
npm run type-check
```

### 6. 代码质量检查

```bash
# 后端
cd backend
black . --check
flake8
mypy .

# 前端
cd frontend
npm run lint
npm run type-check
```

### 7. 常用命令

#### 后端

```bash
# 格式化代码
black .

# 运行特定测试
python -m unittest backend.tests.test_model_gateway -v

# 查看数据库
psql -h localhost -U postgres -d novel_agent
```

#### 前端

```bash
# 构建生产版本
npm run build

# 启动生产服务器
npm start

# 格式化代码
npm run format

# 清理构建缓存
npm run clean
```

### 8. 调试技巧

#### 后端调试

1. **使用断点**:
```python
import pdb; pdb.set_trace()
```

2. **查看日志**:
```bash
docker-compose logs -f backend
```

3. **进入容器**:
```bash
docker-compose exec backend bash
```

#### 前端调试

1. **React DevTools**: 安装浏览器扩展
2. **查看网络请求**: 浏览器开发者工具
3. **调试模式**:
```bash
npm run dev -- --debug
```

### 9. 性能优化

#### 后端

1. **数据库索引**:
```sql
CREATE INDEX CONCURRENTLY idx_chapters_project ON chapters(project_id, chapter_number);
```

2. **缓存策略**:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_story_bible(project_id: str):
    # ...
```

3. **异步处理**:
```python
@app.post("/chapters/generate")
async def generate_chapter():
    task = generate_chapter_task.delay(chapter_id)
    return {"task_id": task.id}
```

#### 前端

1. **代码分割**:
```typescript
const Editor = dynamic(() => import('@/components/editor'), {
  ssr: false,
})
```

2. **图片优化**:
```typescript
import Image from 'next/image'
```

3. **状态管理优化**:
```typescript
// 使用 shallow equal
const { data } = useStore((state) => ({ data: state.data }), shallow)
```

### 10. 部署

#### 生产环境配置

1. **更新环境变量**:
```bash
# .env.production
DATABASE_URL=postgresql://user:pass@prod-db:5432/novel_agent
JWT_SECRET_KEY=<strong-random-key>
LOG_LEVEL=INFO
```

2. **构建 Docker 镜像**:
```bash
docker-compose -f docker-compose.prod.yml build
```

3. **部署**:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### 监控

1. **Prometheus + Grafana**:
```bash
docker-compose up -d prometheus grafana
```

2. **日志收集**:
```bash
docker-compose up -d elasticsearch logstash kibana
```

### 11. 故障排查

#### 常见问题

**问题 1: 数据库连接失败**
```bash
# 检查数据库是否运行
docker-compose ps postgres

# 查看数据库日志
docker-compose logs postgres

# 测试连接
psql -h localhost -U postgres -d novel_agent
```

**问题 2: Celery 任务不执行**
```bash
# 检查 Celery worker 是否运行
docker-compose ps celery

# 查看 Celery 日志
docker-compose logs celery

# 测试任务
celery -A tasks.celery_app inspect ping
```

**问题 3: 向量检索失败**
```bash
# 检查 Qdrant 状态
curl http://localhost:6333/

# 查看集合
curl http://localhost:6333/collections
```

### 12. 贡献指南

1. **Fork 项目**
2. **创建特性分支**: `git checkout -b feature/amazing-feature`
3. **提交更改**: `git commit -m 'Add amazing feature'`
4. **推送到分支**: `git push origin feature/amazing-feature`
5. **开启 Pull Request**

### 13. 相关文档

- [PRD.md](./PRD.md) - 产品需求文档
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - 项目结构说明
- [README.md](./README.md) - 项目说明

---

**最后更新**: 2026-03-18
