# 长篇小说创作 Agent - 全量执行/分步推进 PRD

**版本**: v1.0  
**创建日期**: 2026-03-18  
**状态**: 执行中

---

## 1. 文档目标

这不是面向投资人、产品汇报或需求评审的 PRD，而是面向执行代理的交付文档。  
目标是把现有的产品蓝图，转化为可以直接施工的全量执行方案。

执行要求：
- 按全量架构设计，不按 demo 标准设计
- 按依赖关系分步推进，不并发做互相阻塞的模块
- 每一阶段都必须产出可验证的工程结果
- 所有关键流程必须可观测、可追踪、可解释、可回滚

---

## 2. 当前现状

当前仓库结论：
- 已有产品、开发、目录结构文档
- 目录骨架已规划
- 真实代码基本未落地
- 当前阶段属于 `从 0 到 1 的工程初始化阶段`

因此执行策略不是“迭代现有系统”，而是“按既定蓝图从空仓搭建完整系统”。

---

## 3. 全量目标

项目最终目标不是单点章节生成器，而是完整的长篇小说创作工作台，包含：
- 前端创作工作台
- 后端 API 与鉴权体系
- 多 Agent 编排系统
- Story Bible 长期记忆系统
- 14 维质量评估系统
- AI 味检测与一致性检查
- 反思循环与辩论机制
- 章节版本控制
- 异步任务系统与实时进度
- 用户偏好学习与风格配置
- 多卷本、多分支、多人协作
- 生产级部署、监控、备份与恢复

---

## 4. 执行原则

### 4.1 架构原则

- 先定协议，再写模块
- 先定数据模型，再写业务逻辑
- 先定任务流，再写 Agent
- 先打通主链路，再扩充高级能力

### 4.2 工程原则

- 所有长耗时操作默认异步
- 所有核心对象必须有明确 schema
- 所有新接口必须有统一错误模型
- 所有 Agent 输出必须带结构化结果与推理说明
- 所有章节相关改动必须支持版本追踪

### 4.3 交付原则

- 未通过基础质量门禁的代码不得视为完成
- 未落到仓库的内容不算产出
- 没有测试或最小可验证路径的模块不算完成

---

## 5. 全量执行阶段

| 阶段 | 名称 | 目标 | 核心产出 |
|------|------|------|----------|
| Phase 0 | 技术定版 | 冻结协议与边界 | 数据模型、API 草案、Agent 协议、任务协议 |
| Phase 1 | 工程主干 | 搭建可运行基础设施 | 前后端骨架、Docker、基础配置、健康检查 |
| Phase 2 | 领域数据层 | 建立核心对象与存储 | 模型、迁移、Repository、Service |
| Phase 3 | API 与认证 | 对外暴露稳定接口 | Auth、Projects、Story Bible、Chapters、Tasks、Export |
| Phase 4 | 前端工作台骨架 | 建立可联调前端 | 登录、项目、设定、章节工作区 |
| Phase 5 | Agent 核心系统 | 建立编排与模型调用层 | Agent 基类、消息总线、模型网关、协调器 |
| Phase 6 | 记忆系统 | 建立长期一致性基础 | Story Bible 聚合、Qdrant、上下文构建 |
| Phase 7 | 生成主链路 | 跑通章节生成闭环 | 规划、写作、修订、入库 |
| Phase 8 | 质量评估体系 | 产出结构化评估结果 | 14 维指标、AI 味检测、一致性检查 |
| Phase 9 | 反思循环 | 建立多轮自动改进 | 问题提取、修订计划、辩论、复评 |
| Phase 10 | 前端高级工作台 | 落地完整创作体验 | 评估面板、版本对比、进度、导出 |
| Phase 11 | 高级功能 | 扩展产品深度 | 偏好学习、风格化、多卷本、协作 |
| Phase 12 | 生产化 | 让系统可部署和可运营 | 监控、告警、压测、备份、发布 |

---

## 6. 批次推进方式

### Batch 1

目标：完成 `Phase 0 + Phase 1` 的真实落地

包含：
- 根目录规范
- 前端骨架
- 后端骨架
- 环境变量样例
- Docker Compose
- 健康检查
- 日志、配置、错误模型基础设施

### Batch 2

目标：完成 `Phase 2 + Phase 3`

包含：
- 数据模型
- Alembic 迁移
- 认证
- 项目与 Story Bible API
- 章节和版本 API
- 任务状态 API

### Batch 3

目标：完成 `Phase 4 + Phase 5 + Phase 6`

包含：
- 前端工作台主要页面
- Agent 基类与消息总线
- 模型网关
- Story Bible 聚合
- 向量检索
- 上下文组装

### Batch 4

目标：完成 `Phase 7 + Phase 8 + Phase 9`

包含：
- 章节生成链路
- 结构化评估
- AI 味检测
- 一致性检查
- 反思循环
- 辩论修订

### Batch 5

目标：完成 `Phase 10 + Phase 11 + Phase 12`

包含：
- 高级工作台
- 偏好学习
- 风格化
- 多卷本与分支
- 协作能力
- 监控、部署、恢复

---

## 7. 关键依赖顺序

严禁跳过依赖：

1. `配置/协议` 先于 `业务实现`
2. `数据模型` 先于 `API`
3. `API` 先于 `前端联调`
4. `任务协议` 先于 `异步任务`
5. `Agent 基类` 先于 `具体 Agent`
6. `记忆系统` 先于 `生成主链路`
7. `评估体系` 先于 `反思循环`
8. `观测性` 先于大规模联调

---

## 8. 完成定义

一个阶段只有在以下条件满足后才算完成：

- 代码已落地到仓库
- 本阶段关键路径可运行
- 配置项完整
- 最低限度测试通过
- 相关文档同步更新
- 对外接口具备稳定输入输出结构

---

## 9. Batch 1 的具体执行任务

### 9.1 目标

把当前空仓库推进为“可继续开发的工程项目”。

### 9.2 必须落地内容

- `EXECUTION_PRD.md`
- `.gitignore`
- `backend/requirements.txt`
- `backend/.env.example`
- `backend/api/main.py`
- `backend/core/config.py`
- `backend/core/logging.py`
- `backend/core/errors.py`
- `backend/api/deps.py`
- `frontend/package.json`
- `frontend/.env.example`
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `docker-compose.yml`
- `infrastructure/docker/Dockerfile.backend`
- `infrastructure/docker/Dockerfile.frontend`

### 9.3 验收标准

- 后端可通过 `uvicorn api.main:app --reload` 启动
- 前端可通过 `npm run dev` 启动
- `docker compose up -d` 可拉起基础服务
- 提供 `/health` 和 `/ready` 健康检查
- 基础配置、日志和错误模型已存在

---

## 10. 当前执行状态

当前状态：
- `Phase 0`: 已完成
- `Phase 1`: 已完成
- `Phase 2`: 已完成
- `Phase 3`: 已完成
- `Phase 4`: 已完成
- `Phase 5`: 已完成
- `Phase 6`: 已完成
- `Phase 7`: 已完成
- `Phase 8`: 已完成
- `Phase 9`: 已完成
- `Phase 10`: 已开始
- `Phase 11`: 已开始
- `Phase 12`: 未开始
- `Batch 1`: 已完成
- `Batch 2`: 已完成
- `Batch 3`: 已完成
- `Batch 4`: 已完成
- `Batch 5`: 已开始

已完成项：
1. 执行版 PRD 已落地
2. 前后端基础骨架已建立
3. Docker Compose 与基础 Dockerfile 已建立
4. 后端配置、日志、错误模型已建立
5. 数据库基类、会话、Repository 初版已建立
6. 核心 SQLAlchemy 模型已建立
7. Alembic 迁移环境已建立
8. 首个初始 schema 迁移已落地
9. JWT 安全模块、认证 API、项目 API、Story Bible API、章节与版本 API 已落地
10. 前端登录、注册、仪表板已开始接入真实接口
11. Story Bible 前端工作区已落地
12. 章节列表、章节编辑器、版本回滚前端工作区已落地
13. 任务状态查询与章节生成任务入口骨架已落地
14. Story Bible 聚合读模型已落地
15. 启发式质量评估模块与评估 API 已落地
16. 编辑器已接入任务状态与章节评估展示
17. Agent bus、Agent 基类与 coordinator 已落地
18. architect / librarian / writer / critic / editor 角色骨架已落地
19. 章节生成任务已接入后台异步执行流程
20. 生成结果可自动写回章节、版本与评估记录
21. 任务状态已接入数据库持久化模型与迁移
22. 模型网关接口与本地回退实现已落地
23. 检索式上下文构建器与 lexical vector store 已落地
24. 编辑器可恢复章节最近任务状态
25. 模型网关已补 OpenAI / Anthropic 远程调用路径
26. 任务事件广播与 WebSocket 订阅接口已落地
27. 编辑器已接入任务 WebSocket 实时订阅
28. 模型网关已补超时与重试策略
29. Redis 任务事件通道已接入实时层
30. 编辑器已补版本对比与更完整的生成痕迹展示
31. 任务事件已接入数据库持久化模型、迁移与查询 API
32. 编辑器已补任务时间线面板与事件摘要展示
33. 模型网关已补结构化错误分类并写入 Agent generation metadata
34. 前端依赖安装、TypeScript 检查与 Next.js 生产构建已验证通过
35. 检索层已升级为 Qdrant 优先、lexical fallback 的混合检索实现
36. 后端 dataclass 已移除 slots 参数，兼容 Python 3.9 运行时
37. 临时虚拟环境已完成依赖安装与导入级验证，检索层在无 Qdrant 服务时可安全回退 lexical
38. Redis 事件层已支持无 Redis 降级，本地广播模式下应用可正常启动
39. 后端已补 8 条单元与烟测，覆盖模型错误分类、任务事件摘要、混合检索、应用启动与 Redis 降级
40. Alembic 配置已修正为稳定路径，离线迁移 SQL 生成已验证通过
41. Project / Chapter 导出 API 已落地，支持 Markdown 与 TXT
42. 前端项目卡片、章节工作区与章节编辑器已接入导出下载入口
43. 后端测试已扩展到 12 条，覆盖导出格式、下载响应头与文件名生成
44. 协调器结果已透传 initial_review / final_review / revision_focus 审校回路数据
45. 编辑器已补审校回路面板，可查看初评、复评、修订焦点与遗留问题
46. debate 代理已落地，可把 critic 问题转成 revision_plan 与 debate_summary
47. editor 已接入 revision_plan 输入，修订不再只是基于 issue 列表盲改
48. 编辑器已展示辩论结论、修订计划、动作与验收标准
49. 后端测试已扩展到 13 条，覆盖 debate revision_plan 的结构与优先级
50. approver 终审代理已落地，可输出 approved / release_recommendation / score_delta / blocking_issues
51. 章节生成结果已按终审结论自动落位状态，未通过终审时保留在 `writing`
52. 编辑器已补终审结论面板，可查看终审摘要、流转建议、评分变化与阻塞问题
53. 后端测试已扩展到 14 条，覆盖 approver 输出结构；现有 14 条测试全部通过
54. 高级工作台聚合接口已落地，可汇总项目、章节、活跃任务、质量均值与最近任务
55. 用户级风格偏好模型、迁移与 `/profile/preferences` API 已落地
56. 风格偏好已注入 architect / writer / editor 的生成输入，默认回退文本也会受配置影响
57. 前端工作台已升级为高级总览页，显示项目矩阵、任务摘要与风格偏好快照
58. 前端已新增风格偏好配置页，可编辑文风、视角、节奏、对话比例、张力、感官密度与禁用表达
59. 后端测试已扩展到 17 条，新增 dashboard / preference 单测并全部通过
60. `preference_observations` 偏好观察模型与迁移已落地，可记录章节新建、手动保存与版本回滚产生的风格观察
61. 偏好服务已补内容分析、稳定信号聚合与学习快照摘要，可从人工改写中推断节奏、对话比例、视角、张力、感官密度与偏爱元素
62. 章节新建 / 手动保存 / 回滚已接入偏好学习自动回写，低噪声变更会自动过滤
63. 生成链路已接入“显式偏好 + 学习信号”融合，显式配置稀疏时可用稳定学习结果补全默认风格输入
64. `/profile/preferences` 与 dashboard 偏好快照已透出学习快照，前端可查看观察次数、稳定信号、来源分布与高频保留元素
65. 偏好页已新增“自动学习信号”展示区，可直接查看系统从人工内容变更中学到的约束摘要
66. 后端测试已扩展到 21 条，新增偏好学习推断 / 聚合 / 生成融合单测并全部通过；离线迁移 SQL 生成再次验证通过
67. dashboard 聚合 schema 已扩展项目级质量趋势结构，支持章节评分点、趋势方向、覆盖率、风险章节与评分变化量
68. `/api/v1/dashboard/overview` 已补项目质量趋势摘要，`/api/v1/dashboard/projects/{project_id}/quality-trend` 已落地单项目趋势接口
69. 前端工作台已新增“项目质量趋势”视图区，展示最近章节评分折线、趋势方向、最新分数、覆盖率与风险章节
70. 项目矩阵已补趋势状态与评分变化摘要；后端测试已扩展到 22 条并全部通过
71. 用户偏好模型已补 `active_template_key` 字段与迁移，风格模板现在是正式持久化能力，不再只是前端常量
72. 偏好服务已内置 5 套可复用风格模板，并支持 `replace` / `fill_defaults` 两种应用策略
73. `/api/v1/profile/style-templates`、`/api/v1/profile/style-templates/{template_key}/apply` 与激活模板清除接口已落地
74. `/profile/preferences` 与 dashboard 偏好快照已补激活模板信息，生成风格指导会显式携带当前模板名
75. 前端偏好页已补模板库卡片、覆盖应用、只补默认和取消模板标记能力
76. 后端测试已扩展到 25 条，新增模板应用策略与模板激活测试并全部通过；离线迁移 SQL 生成再次验证通过
77. 项目结构模型已扩展 `ProjectVolume` / `ProjectBranch`，`Chapter` 已正式归属卷与分支，支持多卷本与多分支数据建模
78. 项目服务已补结构自愈能力：项目会自动创建默认卷 `第一卷`、默认分支 `主线`，旧章节会懒回填到默认结构下
79. `/api/v1/projects/{project_id}/structure` 与卷/分支创建更新接口已落地，章节列表 API 已支持按 `branch_id + volume_id` 过滤
80. 章节工作区已升级为结构化前端，可切换当前卷/分支、创建新卷、创建新分支并基于来源分支复制章节
81. 生成 payload、Story Bible 章节摘要与导出服务已补卷/分支语义，项目导出会按分支和卷分组，章节导出元数据已包含结构信息
82. 后端已新增项目结构与结构化导出单测；当前定向单测、Python 编译检查、前端 type-check 与 Alembic 离线 SQL 生成均已通过
83. 项目质量趋势接口已扩展详情级字段，补充区间均分、状态分布、强势章节、薄弱章节、区间范围与可见章节数，支持趋势详情页直接消费
84. `/api/v1/dashboard/projects/{project_id}/quality-trend` 已支持 `chapter_limit` 查询参数，可按最近 8 / 24 / 50 章切换趋势观察窗口
85. 前端已新增项目级质量趋势详情页，可查看大图趋势、强弱章节、风险章节、状态分布与章节级编辑跳转
86. 仪表板趋势卡片与项目矩阵已补“质量详情”入口，首页与详情页共享趋势图表组件与格式化逻辑
87. dashboard 趋势单测已扩展，当前新增后端单测、Python 编译检查与前端 type-check 均已通过
88. 项目协作模型已落地，owner 可按邮箱把已注册用户加入项目，角色覆盖 `owner / editor / reviewer / viewer`
89. 项目、章节、仪表板与任务读取路径已接入协作权限校验，审阅者可评估但不能改稿，查看者保持只读
90. 前端已新增协作者管理页，Story Bible 与章节结构工作区已补角色感知限制
91. 章节审阅数据模型已落地，新增 `chapter_comments` / `chapter_review_decisions` 与 Alembic 迁移，批注与审阅结论会按章节版本留痕
92. `/api/v1/chapters/{chapter_id}/review-workspace` 与批注/审阅结论 API 已落地，支持批注创建、状态切换、删除和人工 verdict 记录
93. 章节编辑器已新增“协作审阅”面板，可基于正文选区创建批注、查看批注列表、查看审阅历史并记录 `通过 / 需修改 / 阻塞` 结论
94. 编辑器已补角色感知只读态，reviewer / viewer 可安全进入审阅视图，owner / editor 保留正文编辑与生成能力
95. 后端测试已扩展到 15 条，新增 review workspace 权限与载荷单测；Python 编译检查、定向后端单测、前端 type-check 与 Alembic 离线 SQL 生成均已通过
96. 章节编辑器已新增“局部重写”工作流，支持正文选区载入、指令输入、结果回写与最近一次改写前后对照展示
97. `/api/v1/chapters/{chapter_id}/rewrite-selection` 已落地，后端会结合风格偏好、Story Bible 上下文与重叠批注只改写选中片段，并自动生成章节新版本
98. 局部重写服务已接入模型网关与本地 fallback，在无远程模型时仍可完成基础片段重写，结果会写回章节并沉淀为偏好学习样本
99. 后端测试已扩展到 19 条，新增 rewrite service 纯函数单测；当前 Python 编译检查、定向后端单测与前端 type-check 均已通过
100. 章节关键节点确认数据模型已落地，新增 `chapter_checkpoints` 与 Alembic 迁移，支持对重要转折、大纲闸口和人工确认点留痕
101. `/api/v1/chapters/{chapter_id}/checkpoints` 与更新接口已落地，owner / editor / reviewer 可在章节内发起确认请求并给出 `approved / rejected / cancelled` 决策
102. review workspace 已聚合关键节点确认数据，章节编辑器右侧审阅面板已新增“关键节点确认”区，可发起确认、查看待确认项并直接做通过/驳回/取消决策
103. 后端测试已扩展到 20 条，新增 checkpoint 聚合顺序与权限断言；当前 Python 编译检查、定向后端单测、前端 type-check 与 Alembic 离线 SQL 生成均已通过
104. 章节审批门禁摘要已打通到 `ChapterRead`、章节列表与章节/项目导出，接口会透出 `pending/rejected/latest checkpoint/final_ready` 等字段，章节工作区可直接看到 Final 阻塞原因
105. 章节状态流转已接入强约束：存在 `pending / rejected checkpoint` 时禁止把章节标记为 `final`；若 `final` 章节被新建、重开或驳回 checkpoint，会自动回落到 `review`
106. 后端已新增 chapter gate 单测与导出断言，当前定向 27 条后端单测、Python 编译检查与前端 type-check 均已通过
107. 章节编辑器已新增显式 `Final Gate` 提示区，保存前会在前端预拦截被 gate 阻塞的 `final` 状态提交，并与右侧审阅刷新保持同步
108. checkpoint 历史已补状态/类型筛选、上下文焦点与“查看关联批注 / 版本上下文”操作，可直接从 checkpoint 回跳到同版本批注和版本对比区
109. 批注列表已支持 checkpoint 上下文过滤与正文选区定位，编辑器内可以沿着 `checkpoint -> comment -> selection` 直接追踪审批链；前端 type-check 已再次通过
110. 最新 `review decision` 已正式接入 final gate：`changes_requested / blocked` 会阻塞章节进入 `final`，并在 `final` 章节上触发状态回落到 `review`
111. 章节读取、章节列表、导出与编辑器 gate 面板已补 `latest_review_verdict / latest_review_summary / review_gate_blocked`，人工审阅不再只是留痕，而是进入真实审批链
112. 编辑器已新增“审阅时间线”面板，把 `comment / review decision / checkpoint` 聚合进单一时间轴，并支持按时间线项回跳正文锚点、批注上下文与版本对比；后端编译检查、定向 21 条后端单测与前端 type-check 均已通过
113. 章节批注已升级为单层线程模型，`chapter_comments` 新增 `parent_comment_id` 自关联字段与迁移；回复回复时后端会自动归并到根批注，存在回复的根批注禁止删除
114. 编辑器批注区已改为线程视图，支持根批注回复、回复回复、内联回复输入框、根批注 `reply_count` 展示与“回复将挂到线程下”提示；审阅时间线也会区分 `新增批注 / 新增回复`
115. 当前线程化改动已完成验证：Python 编译检查通过，`review_service + chapter_gate_service + export_service` 定向 23 条后端单测通过，前端 `npm run type-check` 通过

下一步直接进入：
1. 继续推进 `Phase 11` 的编辑深水区，可把 checkpoint / review decision 的状态变更进一步联动成更细的审批协议，或补批注指派/待办化能力
2. 如需继续完善 `Phase 10`，下一步可补项目间趋势对比视图或章节评分快照筛选能力
3. 在 `Phase 10/11` 深度功能收口后，再回到任务 WebSocket 鉴权、Docker 基础服务和真实联调清扫
