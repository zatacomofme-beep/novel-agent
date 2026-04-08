# 📋 novel-agent 全量深度审查报告 (Phase 5)

> 审查日期：2026-04-06
> 审查范围：全部模块（core/agents/services/api/models/db/memory/bus/tasks/frontend/infra）
> 审查方式：逐文件阅读 + 交叉引用分析

---

## 📊 审查覆盖矩阵

| 模块 | 文件数 | 审查状态 | 关键发现 |
|------|--------|----------|----------|
| **core/** | 18 文件 | ✅ 完成 | 配置/日志/安全/异常/断路器/限流/降级/类型协议 |
| **agents/** | 16 文件 | ✅ 完成 | base/coordinator/model_gateway/output_validator |
| **services/** | 44 文件 | ✅ 完成 | workflow(3200行God File)/neo4j/prompt_cache/auth/project/chapter |
| **api/** | 15 文件 | ✅ 完成 | main/ws/router/auth/projects/deps/rate_limit |
| **models/** | 35+ 文件 | ✅ 完成 | user/project/chapter/refresh_token |
| **db/** | 5 文件 | ✅ 完成 | session/base/repository/migrations |
| **memory/** | 7 文件 | ✅ 完成 | L1/L2/L3/story_bible/vector_store/context_builder |
| **bus/** | 3 文件 | ✅ 完成 | protocol/message_bus/events |
| **tasks/** | 5+ 文件 | ✅ 完成 | celery_app/chapter_generation/state_store/schemas |
| **frontend/** | 核心文件 | ✅ 完成 | auth/api-client/security/next.config |
| **infra** | docker-compose | ✅ 完成 | 7个服务编排 |

---

## 🔴 新发现问题清单

### P0 — 架构风险（需决策后执行）

#### #21 God File: story_engine_workflow_service.py 膨胀至 3200+ 行

- **严重度**: 🔴 Critical
- **位置**: [story_engine_workflow_service.py](backend/services/story_engine_workflow_service.py)
- **现状**: 单文件包含 5 个工作流（outline_stress_test / realtime_guard / knowledge_guard / bulk_import_guard / chapter_stream）+ 50+ 私有函数 + 6 个 TypedDict 状态类
- **影响**:
  - 可维护性极差：修改一个工作流可能意外影响其他工作流
  - 测试困难：无法单独测试子流程
  - 协作冲突：多人同时修改同一文件概率极高
- **建议拆分方案**:
  ```
  services/
  ├── story_engine_workflows/
  │   ├── __init__.py
  │   ├── outline_stress.py      # ~400行
  │   ├── realtime_guard.py       # ~500行
  │   ├── knowledge_guard.py      # ~600行
  │   ├── bulk_import_guard.py    # ~300行
  │   ├── chapter_stream.py       # ~800行
  │   └── shared_utils.py         # ~300行（公共工具函数）
  ```
- **工作量**: 3-5 天

#### #22 L1/L3 内存系统无持久化 + 无容量上限

- **严重度**: 🔴 High
- **位置**: [l1_working.py](backend/memory/l1_working.py), [l3_long_term.py](backend/memory/l3_long_term.py)
- **现状**:
  - `L1WorkingMemory`: 纯内存 dict，进程重启即丢失，无条目数限制
  - `L3LongTermMemory`: 纯内存 dict，同样无持久化、无容量控制
  - 两者均为 Singleton 模式，但无线程安全的写保护（L1 的 `store`/`add_session_event` 非原子操作）
- **影响**:
  - 长时间运行后内存持续增长（OOM 风险）
  - 进程崩溃/重启丢失所有上下文
  - 并发写入可能导致数据竞争
- **修复方案**:
  - 添加 `max_entries` 配置项 + LRU 淘汰策略
  - 关键状态定期快照到 Redis/数据库
  - 写操作加 `threading.RLock` 保护

---

### P1 — 重要缺陷（应尽快修复）

#### #23 datetime.utcnow() 已废弃 — 多处使用

- **严重度**: 🟠 High
- **位置**:
  - [l1_working.py:28](backend/memory/l1_working.py#L28) — `created_at: datetime = field(default_factory=datetime.utcnow)`
  - [l2_episodic.py:48](backend/memory/l2_episodic.py#L48) — `default=datetime.utcnow`
  - [l2_episodic.py:52](backend/memory/l2_episodic.py#L52) — `onupdate=datetime.utcnow`
  - [l3_long_term.py:33](backend/memory/l3_long_term.py#L33) — `default_factory=datetime.utcnow`
- **影响**: Python 3.12+ 废弃警告，未来版本将移除；返回 naive datetime 导致时区混乱
- **修复**: 全部替换为 `datetime.now(timezone.utc)`

#### #24 InMemoryMessageBus 无容量限制 — 内存泄漏风险

- **严重度**: 🟠 Medium-High
- **位置**: [message_bus.py](backend/bus/message_bus.py)
- **现状**: `_events: list[BusEvent]` 无限追加，长期运行后持续增长
- **修复**: 添加 `max_events` 配置（默认 10000），超出时截断或循环覆写

#### #25 RateLimiter 无连接池管理 — 连接泄漏

- **严重度**: 🟠 Medium
- **位置**: [rate_limit.py](backend/core/rate_limit.py)
- **现状**:
  - 每次 `_get_redis()` 创建新连接（如果为 None）
  - `close()` 方法存在但从未在应用生命周期中调用
  - 无连接复用机制
- **修复**: 使用 `redis.ConnectionPool` 或在 app lifespan 中管理生命周期

#### #26 auth.py 中 import 放置在文件末尾 — 代码风格问题

- **严重度**: 🟡 Low-Medium
- **位置**: [auth.py:148](backend/api/v1/auth.py#L148)
- **现状**: `from core.errors import AppError` 放在文件末尾（第148行），而非顶部
- **影响**: IDE 无法正确解析依赖，可能导致运行时 ImportError
- **修复**: 移到文件顶部 import 区域

#### #27 register_user / login 直接 commit 未使用 transactional()

- **严重度**: 🟠 Medium
- **位置**: [auth_service.py](backend/services/auth_service.py)
- **现状**:
  - `register_user()`: 直接 `session.commit()` + `session.refresh()`
  - `authenticate_user()`: 无事务包装
- **影响**: 与 Phase 1 建立的 `transactional()` 上下文管理器不一致，无法享受统一回滚机制
- **修复**: 改用 `async with transactional(session):` 包装

#### #28 projects.py API 路由文件过大（1157+ 行）

- **严重度**: 🟡 Medium
- **位置**: [projects.py](backend/api/v1/projects.py)
- **现状**: 单文件包含 30+ 个端点，涵盖 CRUD/生成/协作/导出/StoryBible/分支/卷等所有项目操作
- **影响**: 与 #21 类似的 God File 问题（虽不如 workflow 严重）
- **建议拆分**:
  ```
  api/v1/
  ├── projects_crud.py     # 基本 CRUD
  ├── projects_gen.py      # 生成相关端点
  ├── projects_collab.py   # 协作/权限
  └── projects_export.py   # 导出功能
  ```

---

### P2 — 安全加固

#### #29 Refresh Token 明文返回给客户端

- **严重度**: 🟠 Medium-High
- **位置**: [auth.py:85-95](backend/api/v1/auth.py#L85-L95), [auth.py:110-120](backend/api/v1/auth.py#L110-L120)
- **现状**: 注册和登录接口直接将 `rt_hash`（SHA256 哈希后的 token 值）作为 `refresh_token` 返回
  ```python
  return TokenResponse(
      access_token=access_token,
      refresh_token=rt_hash,  # ← 这是哈希值本身，不是原始token
      ...
  )
  ```
- **分析**: 当前实现是哈希值存储在DB，哈希值返回给客户端。这意味着：
  - 如果 DB 泄露，攻击者可以直接用存储的哈希值冒充 refresh token
  - 正确做法应该是：DB 存哈希，返回原始 token 给客户端
- **修复**: 返回原始 `raw = secrets.token_urlsafe(32)` 值，DB 存 `hashlib.sha256(raw).hexdigest()`

#### #30 CORS 配置中 localhost 白名单硬编码

- **严重度**: 🟡 Low-Medium
- **位置**: [next.config.js:37](frontend/next.config.js#L37)
- **现状**: CSP `connect-src` 包含 `ws://localhost:* wss://localhost:* http://localhost:* https://localhost:*`
- **影响**: 生产环境不应允许 localhost 连接
- **修复**: 通过环境变量动态生成 CSP 头

#### #31 WebSocket 认证 Token 可选传递 — 安全隐患

- **严重度**: 🟠 Medium
- **位置**: [ws.py:80-90](backend/api/ws.py#L80-L90)
- **现状**: 
  ```python
  token = websocket.cookies.get(AUTH_TOKEN_KEY)
  if not token:
      token = await receive_ws_token(websocket)  # 从消息体获取
  ```
- **影响**: 允许通过非 cookie 方式传递 token，增加 CSRF 风险
- **修复**: 生产环境强制仅从 Cookie 读取 token

---

### P3 — 性能优化

#### #32 PROJECT_RELATIONS 过度预加载 — N+1 反模式变体

- **严重度**: 🟡 Medium
- **位置**: [project_service.py:130-155](backend/services/project_service.py#L130-L155)
- **现状**: `PROJECT_RELATIONS` 包含 15 个 `selectinload`，每次加载项目都会 JOIN 大量关联表
- **影响**: 项目列表接口响应慢，数据库压力大
- **修复**: 
  - 区分"列表视图"和"详情视图"的加载策略
  - 列表只加载必要字段，详情按需加载关联

#### #33 story_engine_workflow_service.py 中大量字符串拼接构建 prompt

- **严重度**: 🟡 Low-Medium
- **位置**: [story_engine_workflow_service.py](backend/services/story_engine_workflow_service.py) 多处
- **现状**: 使用 f-string 拼接大量 prompt 文本（如 `_build_story_knowledge_guard_context_text` 返回 5200 字符的字符串）
- **影响**: 内存分配频繁，难以维护和测试 prompt 模板
- **修复**: 使用 Jinja2 或 string.Template 管理 prompt 模板

#### #34 model_gateway.py generate_text_sync 中的 ThreadPoolExecutor 每次创建新实例

- **严重度**: 🟡 Low
- **位置**: [model_gateway.py:310-320](backend/agents/model_gateway.py#L310-L320)
- **现状**: 每次 sync 调用都创建新的 `ThreadPoolExecutor(max_workers=1)`
- **影响**: 线程资源浪费
- **修复**: 使用类级别或模块级别的 executor 实例

---

### P4 — 代码质量

#### #35 Optional 导入未统一使用 typing.Optional

- **严重度**: 🟢 Low
- **位置**: [errors.py:14](backend/core/errors.py#L14), [protocol.py:19](backend/bus/protocol.py#L19), [l2_episodic.py:17](backend/memory/l2_episodic.py#L17)
- **现状**: 部分文件使用 `from typing import Optional`，部分使用 `typing.Optional`（Python 3.10+ 已内置）
- **修复**: 统一使用内置 `Optional`（需 Python 3.10+）

#### #36 bus/protocol.py 使用 dataclass 但缺少 __repr__ 自定义

- **严重度**: 🟢 Low
- **位置**: [protocol.py](backend/bus/protocol.py)
- **现状**: `AgentMessage` 包含 `content: dict[str, Any]`，默认 repr 会输出完整内容（可能很长）
- **修复**: 添加自定义 `__repr__` 截断敏感字段

#### #37 前端 apiFetch 默认不携带 Authorization Header

- **严重度**: 🟠 Medium
- **位置**: [api-client.ts:82-92](frontend/lib/api-client.ts#L82-L92)
- **现状**: `apiFetch()` 不带 token，只有 `apiFetchWithAuth()` 带 token
- **影响**: 开发者容易误用 `apiFetch()` 访问需要认证的接口，只在 401 时才触发 refresh 流程（多一次网络往返）
- **修复**: 统一入口或在文档中明确区分使用场景

---

## 📈 问题优先级总览

```
P0 架构风险:
  #21  story_engine_workflow_service.py God File (3200行)     ← 需架构决策
  #22  L1/L3 Memory 无持久化 + 无容量上限                      ← 需架构决策

P1 重要缺陷:
  #23  datetime.utcnow() 废弃                                  ← 可立即修
  #24  InMemoryMessageBus 无容量限制                            ← 可立即修
  #25  RateLimiter 连接泄漏                                     ← 可立即修
  #26  auth.py import 位置错误                                   ← 可立即修
  #27  auth_service 未使用 transactional()                      ← 可立即修
  #28  projects.py 路由文件过大                                 ← 需规划拆分

P2 安全加固:
  #29  Refresh Token 返回哈希值而非原始值                       ← 应尽快修
  #30  CSP localhost 硬编码                                     ← 可立即修
  #31  WebSocket Token 可选传递                                 ← 可立即修

P3 性能优化:
  #32  PROJECT_RELATIONS 过度预加载                             ← 需性能测试验证
  #33  Prompt 字符串拼接                                       ← 低优先级
  #34  ThreadPoolExecutor 重复创建                              ← 低优先级

P4 代码质量:
  #35  Optional 导入不一致                                     ← 可顺手修
  #36  AgentMessage __repr__ 缺失                              ← 可顺手修
  #37  apiFetch vs apiFetchWithAuth 混淆风险                   ← 需文档/重构
```

---

## 🔗 与历史问题的关系

| 新编号 | 关联旧问题 | 关系 |
|--------|-----------|------|
| #21 | PHASE4 #15 (run_chapter_stream nonlocal变量) | 同一根源：workflow service 膨胀 |
| #22 | PHASE4 #14 (Prompt Cache LRU) | 同类问题：内存管理 |
| #23 | — | 全新发现 |
| #29 | PHASE4 #17 (XSS 加固) | 同属安全域 |

---

## ✅ 本次审查确认已修复的问题（Phase 1-4）

以下问题经确认已正确修复：
- ✅ Circuit Breaker TTL + LRU 淘汰
- ✅ Model Gateway 线程安全
- ✅ 99处 commit → transactional()（除 auth_service 残留 #27）
- ✅ JWT Refresh Token 完整链路
- ✅ 注册限流 Redis-backed
- ✅ CSP + XSS 防护
- ✅ 日志脱敏 RedactingFormatter
- ✅ DegradedResponse 统一降级
- ✅ Magic Numbers → Settings 配置化
- ✅ Neo4j/Redis Protocol 类型定义