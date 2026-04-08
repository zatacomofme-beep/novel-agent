# 📋 novel-agent 剩余问题修复跟踪

> 基于 `PROJECT_ISSUES_REPORT.md` 20 个问题的修复进度
> 创建日期：2026-04-06
> Phase 1-3 已完成 11/20，本文档追踪剩余 **9 个未完成/部分完成** 问题

---

## ✅ 已完成（Phase 1-3）

| # | 问题 | 状态 | 修复方式 |
|---|------|------|----------|
| 3 | 99 处散落 commit 无事务管理 | ✅ 完成 | `db/session.py` → `transactional()` 上下文管理器 |
| 4 | Circuit Breaker 内存泄漏 | ✅ 完成 | TTL + LRU + max_records_per_chapter |
| 5 | Model Gateway 线程安全 | ✅ 完成 | 移除全局 event_loop 修改 |
| 7 | 流式生成变量重复赋值 | ✅ 完成 | 删除 copy-paste 残留代码 |
| 8 | Docker 默认密码/无认证 | ✅ 完成 | 环境变量 + Redis auth |
| 10 | JWT 无 Refresh Token | ✅ 完成 | 完整 token rotation 链路 |
| 11 | 注册接口无限流 | ✅ 完成 | Redis-backed rate limiter |
| 19 | 核心 API 路由缺测试 | ✅ 完成 | `test_core_api_routes.py` |
| 20 | DraftStudio 37 props drilling | ✅ 完成 | `DraftStudioContext` API |

---

## 🔧 剩余问题清单（Phase 4）

### P0 — 架构级（需规划决策）

#### #1 Legacy 双轨制并行运行
- **严重度**: 🔴 高 | **影响**: 全局
- **现状**: `legacy_generation_service.py` 冻结但 Celery Task (`tasks/chapter_generation.py`) 仍直接引用
- **待办**:
  - [ ] 设定废弃时间线（建议 2-3 迭代）
  - [ ] 将 legacy 路由返回 `410 Gone` 从配置开关改为硬编码
  - [ ] 迁移 Celery Task 到 Story Engine Workflow
  - [ ] 删除 `legacy_generation_service.py` 及兼容层
- **涉及文件**:
  - `backend/services/legacy_generation_service.py` (删除)
  - `backend/services/legacy_generation_dispatch_service.py` (删除)
  - `backend/tasks/chapter_generation.py` (修改入口)
  - `backend/api/v1/story_engine.py` (移除 deprecation 开关)

#### #2 God File 拆分（6000+ 行 workflow_service）
- **严重度**: 🔴 高 | **影响**: 可维护性
- **现状**: `story_engine_workflow_service.py` 包含大纲压力测试/实时守护/流式生成/终稿优化等完全不同职责
- **待拆分目标结构**:
  ```
  services/
  ├── story_engine/
  │   ├── __init__.py
  │   ├── outline_stress_service.py      # ~200 行
  │   ├── realtime_guard_service.py       # ~300 行
  │   ├── chapter_stream_service.py       # ~500 行
  │   ├── final_optimize_service.py       # ~400 行
  │   ├── checkpoint_resume_service.py    # ~80 行
  │   ├── stream_enrichment.py            # enrichment 逻辑
  │   └── workflow_common.py              # 共享工具函数
  ```

---

### P2 — 可立即推进

#### #6 异常捕获精确化（~80 处残余）
- **严重度**: 🟡 中高 | **影响**: 可调试性 / 错误追溯
- **现状**: Phase 2 引入了 `NovelAgentError` 层次结构框架，但全项目仍有 ~80 处裸 `except Exception`
- **高危文件清单**:
  | 文件 | 裸 except 数量 | 优先级 |
  |------|---------------|--------|
  | `services/prompt_cache_service.py` | 5 处 `pass` | 🔴 最高 |
  | `services/neo4j_service.py` | 7 处宽泛捕获 | 🔴 高 |
  | `services/story_engine_workflow_service.py` | 5 处裸 except | 🔴 高 |
  | `agents/model_gateway.py` | 1-2 处 | 🟡 中 |
  | `services/world_building_service.py` | 2-3 处 | 🟡 中 |
- **修复策略**: 逐文件替换为精确异常类型 + 结构化日志

#### #9 外部服务降级策略不统一
- **严重度**: 🟡 中 | **影响**: 运维可观测性
- **现状**: Neo4j 返回 None, PromptCache 返回 None, Open Threads 返回 [], Social Topology 返回 {} — 无法区分"无数据"和"服务故障"
- **修复方案**: 引入 `DegradedResponse[T]` 统一包装类
- **涉及文件**:
  - `backend/services/neo4j_service.py`
  - `backend/services/prompt_cache_service.py`
  - `backend/services/story_engine_workflow_service.py` (enrichment 部分)

#### #12 N+1 查询 / Agent 串行调用链过长
- **严重度**: 🟡 中 | **影响**: 响应延迟
- **现状**: Coordinator → Writer → Critic → CanonGuardian → Debate 全串行
- **优化方向**:
  - Writer + Critic 可并行（Critic 不依赖 Writer 的 DB 写入结果）
  - CanonGuardian 校验可与 Debate 第一轮并行
  - 需引入 `asyncio.gather` 重构 coordinator.run()

#### #13 Magic Numbers 提取（~20 处散落）
- **严重度**: 🟡 中 | **影响**: 运维灵活性
- **已提取** (Phase 3): CircuitBreaker 默认值、Celery retry 参数
- **剩余散落位置**:
  | 位置 | 当前值 | 含义 | 目标 |
  |------|--------|------|------|
  | `coordinator.py` | `max_revision_rounds=3` | 最大修订轮次 | Settings.REVISION_MAX_ROUNDS |
  | `model_gateway.py` | `timeout=300` | 同步超时(秒) | Settings.LLM_TIMEOUT_SECONDS |
  | `workflow_service.py` | `summary[:220]` | 摘要截断 | SUMMARY_TRUNCATE_LENGTH |
  | `workflow_service.py` | `summary[:300]` | 摘要最大长度 | SUMMARY_MAX_LENGTH |
  | `model_gateway.py` | FALLBACK_CHAIN dict | Fallback 链 | Settings.FALLBACK_CHAIN_JSON |
  | `circuit_breaker.py` | 多处默认值 | 各阈值 | 已部分迁移 |

#### #14 Prompt Cache 内存无上限
- **严重度**: 🟡 中 | **影响**: OOM 风险
- **现状**: 内存缓存 dict 无 eviction 策略；Redis 缓存有 TTL 但内存层无限增长
- **修复方案**:
  - 内存缓存加 `max_entries` 上限 + LRU 淘汰
  - 单条 entry 大小限制（防超大 prompt 占用过多内存）
- **涉及文件**: `services/prompt_cache_service.py`

---

### P3 — 低优先级但值得做

#### #15 Token 估算粗糙（字符÷2）
- **严重度**: 🟢 低 | **影响**: 成本核算精度
- **现状**: `len(text) // 2` 作为 token 数估算，实际误差可达 ±50%
- **方案**: 引入 tiktoken 或各 provider SDK 的 tokenizer

#### #16 类型安全漏洞（~90 处 Any）
- **严重度**: 🟡 中 | **影响**: IDE 支持 / 重构安全
- **重灾区**:
  - `neo4j_service.py`: ~20 处 Any（neo4j Driver 类型缺失 stub）
  - `prompt_cache_service.py`: ~6 处（Redis 动态导入）
  - `story_engine_workflow_service.py`: ~50+ 处（TypedDict total=False）
  - `social_topology_service.py`: ~10 处
  - `model_gateway.py`: ~5 处
- **方案**: 安装 type stubs + 补充 Protocol/TypedDict 定义

#### #17 前端 Token 存储 XSS 加固
- **严重度**: 🟡 中 | **影响**: 安全
- **现状**: Token 存储在 localStorage，XSS 攻击可窃取
- **方案**:
  - 后端: Set-Cookie with httpOnly + SameSite=Strict
  - 前端: 移除 localStorage 存 token，改用 cookie 自动携带
  - CSP header 强化: `script-src 'self'`

#### #18 流式生成闭包变量过多（15+ nonlocal）
- **严重度**: 🟢 低中 | **影响**: 可维护性
- **现状**: `run_chapter_stream()` 内有 15+ nonlocal 变量
- **方案**: 提取为 `StreamState` 数据类，方法改为 StreamState 的方法

---

## 📊 进度统计

```
总计: 20 个问题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 已完成:  11 个 (55%)
⚠️ 部分完成:  2 个 (#6 异常收敛框架, #9 输出校验)
❌ 未开始:   7 个

按优先级:
  P0 (架构): 2 个未开始  ── 需决策后执行
  P2 (重要): 5 个可推进  ── 本阶段目标
  P3 (改善): 2 个低优先级  ── 有空再做
```
