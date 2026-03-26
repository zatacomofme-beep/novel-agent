# 实施任务表

基于 2026-03-26 当前仓库状态整理。

这份文档不是 PRD，也不是泛化建议，而是后续开发时直接对照执行的任务表。
目标是把“哪些已经做完、哪些正在收口、哪些可以后做、哪些暂不做”说清楚。

当前这份文档分为两部分：

- 上半部分是 `V1` 归档记录，保留第一轮主链收口的真实进度。
- 文末的 `第二版实施任务表（当前有效）` 是后续继续开发时要执行的唯一有效顺序。

---

## 固定边界

当前实现必须始终遵守这几条，不再反复摇摆：

- 写手前台只保留一条主路径：
  `创建项目 -> 生成三级大纲 -> 生成/手写正文 -> 精修/收口 -> 终稿确认 -> 自动沉淀设定 -> 进入下一章`
- 前台必须极简，后台可以复杂，但不能把 `Agent`、模型路由、检索、辩论等术语暴露给写手。
- 模型组合、路由策略、后台参数属于管理员能力，不属于写手前台。
- 当前阶段不做内容合规前台链路、不做会员充值、不做 B 端白标。
- 所有主功能优先收口到 `story-room`，避免旧页面重新成为主入口。

### 执行规则

- 后续每次修复和改进，都必须先对照这份任务表确定所属任务，再开始实现。
- 如果实际进度与任务表不一致，先更新这份任务表，再继续开发。
- 不新增脱离主路径的新页面、新入口、新流程，除非任务表明确要求。
- 每次完成一项收口，都要回写这份任务表的状态和当前判断。

---

## 状态说明

| 状态 | 含义 |
| --- | --- |
| `已完成` | 已经可用，且已并入当前主链 |
| `已完成（第一版）` | 主流程已打通，但后续仍可继续精修 |
| `进行中` | 已开始收口，后面几轮继续补 |
| `待开始` | 还没进入具体实现 |
| `暂不做` | 当前阶段明确不投入 |

---

## 当前里程碑总览

| 里程碑 | 状态 | 说明 |
| --- | --- | --- |
| 单工作台主链收口 | `已完成（第一版）` | `dashboard -> story-room -> 大纲 -> 正文 -> 终稿 -> 设定 -> 下一章` 已打通 |
| 编辑器升级 | `已完成（第一版）` | 已从普通输入框升级为类纸面编辑器，支持选区读取与片段改写 |
| 多卷 / 分支前台 | `已完成（第一版）` | `story-room` 已支持卷、分线、章节范围切换 |
| 协作前台 | `已完成（第一版）` | 成员管理页已可用，不再只是跳转占位 |
| 数据安全升级 | `已完成（第一版）` | 本机保稿已升级到 `IndexedDB 优先 + localStorage 兜底 + 恢复列表 + 断网提示` |
| 深度审校并入主工作台 | `已完成` | 版本、批注、确认点、片段改写、回退已并入正文后的“精修台” |
| 终稿后进入下一章 | `已完成` | 已支持“确认保存这一章”与“确认并去下一章”两条路径 |

---

## 必须先做

这些任务直接影响写手主路径是否足够顺、是否能长期稳定使用。

| ID | 任务 | 状态 | 优先级 | 目标 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `P0-01` | 新建书后的默认动作继续降噪 | `已完成` | `P0` | 创建项目后让用户一眼知道先做什么，避免入口重叠、路径犹豫 | `frontend/app/dashboard/page.tsx` `frontend/app/page.tsx` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` |
| `P0-02` | 新章进入正文区后的主按钮继续压缩 | `已完成（第一版）` | `P0` | 把“生成第一版正文 / 保存本章 / 检查并收口 / 去精修台”做得更直白，减少状态理解成本 | `frontend/components/story-engine/draft-studio.tsx` |
| `P0-03` | 终稿、章节总结、设定沉淀的复用出口收口 | `已完成（第一版）` | `P0` | 让章节总结、设定更新、终稿确认的结果更自然地服务下一章，而不是停在展示层 | `frontend/components/story-engine/final-diff-viewer.tsx` `frontend/components/story-engine/final-publish-panel.tsx` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` |
| `P0-04` | 设定与正文的双向定位 | `已完成（第一版）` | `P0` | 从正文选中人物/物品/规则能跳到设定，从设定条目能回到关联章节位置 | `frontend/components/story-engine/knowledge-base-board.tsx` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `backend/api/v1/story_engine.py` |
| `P0-05` | 主链手工 smoke 用例固化 | `已完成（第一版）` | `P0` | 把“开书 -> 大纲 -> 正文 -> 精修 -> 终稿 -> 下一章”沉成一份固定冒烟清单，减少后续回归成本 | `docs/architecture/implementation-task-table.md` `docs/architecture/current-priority-checklist.md` |

### `P0-01` 验收标准

- 创建项目后只保留一个明显主动作。
- 用户不需要猜“先写正文”还是“先测漏洞”。
- 首页、项目列表、工作台入口文案保持一致。

### `P0-02` 验收标准

- 新开章节时，用户能直接知道当前应该点哪个按钮。
- 不同状态下主按钮不产生语义重叠。
- 不依赖阅读大段说明文字也能完成“起稿 -> 保存 -> 精修 -> 收口”。

### `P0-01` 当前进度

- 已完成：首页、项目总览、故事工作台的主动作已经统一为“先定三级大纲 / 开始第一章 / 继续写作 / 去终稿收口”。
- 已完成：项目卡片不再出现“继续整理这本书”这类模糊动作，改为基于项目状态直接给出下一步。
- 已完成：创建新书区域的提示文案已压缩，创建后默认直接进入三级大纲。

### `P0-02` 当前进度

- 已完成（第一版）：正文区已改成“一个主按钮 + 最多两个次按钮”的动作结构。
- 已完成（第一版）：主动作已按状态压缩为“先定本章三级大纲 / 生成正文 / 保存本章 / 检查并收口 / 去确认终稿”。
- 已完成（第一版）：正文区四步状态卡与提示文案已压短，减少了同时出现的大量并列说明。

### `P0-03` 验收标准

- 终稿确认后，用户能自然进入下一章。
- 章节总结和设定更新不只是展示，而是可被下一章直接消费。
- 终稿区不再出现“结果很多，但不知道下一步怎么做”的情况。

当前进度：

- 已完成（第一版）：终稿区已支持“确认保存这一章”与“确认并去下一章”。
- 已完成（第一版）：下一章生成时会优先读取章节总结，并带入已确认的设定变动，不再只依赖上一章全文。
- 已完成（第一版）：终稿区已补充“会自动带去下一章”的上下文预览，用户能更直观看到哪些结果会被继续复用。

### `P0-04` 验收标准

- 设定条目与正文位置存在真实跳转关系。
- 修改关键设定后，用户能更快定位受影响章节。
- 不把这套能力做成新页面，优先收口到 `story-room`。

### `P0-04` 当前进度

- 已完成（第一版）：正文区支持“选中文字 -> 去设定里定位”，优先命中本地人物/物品/规则/剧情线，找不到时自动带着关键词进入设定搜索。
- 已完成（第一版）：设定条目支持“一键回正文定位”，优先跳到直接关联章节，其次按正文命中内容回跳。
- 已完成（第一版）：整套双向定位都收口在 `story-room` 内，没有新增分叉页面。

### `P0-05` 验收标准

- 至少覆盖 1 条单人写作主链。
- 至少覆盖 1 条分线/多卷链路。
- 至少覆盖 1 条断网恢复/本机稿恢复链路。

### `P0-05` 当前进度

- 已完成（第一版）：已把单人主链、多卷 / 分线链路、本机稿恢复链路固化到 [current-priority-checklist.md](/Users/libenshi/Desktop/novels/docs/architecture/current-priority-checklist.md)。
- 已完成（第一版）：后续每次较大改动后，都可以直接按这份清单回归，不再依赖口头记忆。

---

## 可以后做

这些项重要，但不会阻塞当前主路径继续收口。

| ID | 任务 | 状态 | 优先级 | 说明 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `P1-01` | 管理员模型路由 / 策略页 | `已完成（第一版）` | `P1` | 只给管理员，不给写手前台 | `backend/api/v1/model_routing.py` `frontend/app/dashboard/admin/model-routing/page.tsx` |
| `P1-02` | 实体生成并入统一任务链 | `已完成（第一版）` | `P1` | 实体补全已并入项目任务链，并回写阶段事件与执行轨迹 | `backend/services/entity_generation_service.py` `backend/tasks/entity_generation.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` |
| `P1-03` | Dashboard 创作数据深化 | `已完成（第一版）` | `P1` | 已有概览和趋势，但还没做成真正的创作效率与质量总览 | `backend/services/dashboard_service.py` `frontend/app/dashboard/page.tsx` |
| `P1-04` | 独立风格中心 | `已完成（第一版）` | `P1` | 已拆出独立入口，同时保留 `story-room` 内嵌轻量面板 | `frontend/components/story-engine/style-control-panel.tsx` `frontend/app/dashboard/preferences/page.tsx` |
| `P1-05` | 移动端轻量化创作模式 | `已完成（第一版）` | `P1` | `story-room` 已补齐手机端轻量模式，主写作链不再只是桌面页面缩放 | `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/components/story-engine/draft-studio.tsx` |

### `P1-01` 当前进度

- 已完成（第一版）：后端已新增 `/api/v1/admin/model-routing/...` 管理员专用接口，项目列表、详情、保存策略都已独立出来。
- 已完成（第一版）：权限边界已收口到后端邮箱白名单，非管理员账号会直接 `403`，写手前台不会暴露模型组合入口。
- 已完成（第一版）：前端已补齐 `/dashboard/admin/model-routing` 后台页，支持按项目切换组合、单职责微调、恢复默认、清空微调与保存。

### `P1-02` 当前进度

- 已完成（第一版）：实体补全服务已改成统一补全管线，会读取项目级模型路由，并按职责候选链自动切换补全模型。
- 已完成（第一版）：实体任务现在会把执行轨迹、回退情况、上下文快照写入 `task result` 和 `task events`，不再只是返回一个最终候选数组。
- 已完成（第一版）：`story-room` 设定区已接入实体补全事件时间线，写手能直接看到“已装载设定 / 正在生成 / 结果已备好”的完整过程。

### `P1-03` 当前进度

- 已完成（第一版）：Dashboard 总览接口现在会额外返回 `activity_snapshot / quality_snapshot / task_health / pipeline_snapshot / genre_distribution / focus_queue`，不再只有总量和走势。
- 已完成（第一版）：首页看板已经改成“近 7 天活跃项目 / 更新章节 / 活跃字数 / 风险章节 + 当前最该处理 + 阶段与任务 + 题材分布”的结构，更像创作工作台，而不是松散信息堆叠。
- 已完成（第一版）：聚合指标明确区分真实统计与代理指标，例如“最近活跃字数”使用最近更新章节的当前字数汇总，避免伪造精确时序。
- 已完成（第一版）：Dashboard 的后端聚合与前端展示已经有类型与测试兜底，后续再做精修时不需要重拆契约。

### `P1-04` 当前进度

- 已完成（第一版）：`/dashboard/preferences` 已从跳转占位改成真实可用的独立风格中心，能直接读取和保存长期偏好、套用声音底稿、清空当前底稿。
- 已完成（第一版）：`StyleControlPanel` 已支持 `story-room / center` 两种模式，正文区保留轻量入口，整本书级的长期手感集中到独立页面收口。
- 已完成（第一版）：书架已补入风格中心入口，`story-room` 内也能直接跳过去细调，并支持通过 `projectId` 回到当前故事工作台。
- 已完成（第一版）：风格样文已在独立风格中心做本地持久化，避免用户切页后丢掉长期校准文本。

### `P1-05` 当前进度

- 已完成（第一版）：`story-room` 已新增移动端底部固定阶段栏，手机上可以一只手切换“大纲 / 正文 / 终稿 / 设定”，并随时触发当前推荐动作。
- 已完成（第一版）：故事工作台顶部的阶段卡、卷线区和正文辅助面板已改成移动端轻模式，默认先看主写作区域，重区块改为按需展开。
- 已完成（第一版）：正文页的“本章进度 / 写作保护 / 实时提醒 / 本章总结”已在移动端折叠收口，不再把桌面右侧整列原样堆到手机长页里。
- 已完成（第一版）：精修台在移动端已改成折叠打开，桌面端仍保留完整展开态，保证跨端操作习惯一致但信息密度不同。

---

## 下一阶段任务

当前 `P0 / P1 / E1` 已完成第一轮主链收口，下面这组任务进入下一阶段。
它们的目标不是重开新流程，而是在不破坏现有单工作台主链的前提下，继续补齐“跨端续写、任务回放、持久化观测”三块能力。

| ID | 任务 | 状态 | 优先级 | 说明 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `P2-01` | 跨端云端续写草稿 | `已完成（第一版）` | `P2` | 在本机保稿之外补齐云端暂存，让桌面和手机能接着写同一章 | `backend/api/v1/story_engine.py` `backend/services/story_engine_cloud_draft_service.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/components/story-engine/draft-studio.tsx` |
| `P2-02` | 工作台任务轨迹与流程回放 | `已完成（第一版）` | `P2` | 把已有 `workflow_timeline / task_runs / task_events` 更完整地收口到 `story-room` 与 `dashboard` | `backend/api/v1/tasks.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/app/dashboard/page.tsx` |
| `E2-01` | 章节工作流持久化并轨到任务系统 | `已完成（第一版）` | `P2` | 让章节流式生成、实时守护、终稿收口不仅返回时间线，还沉到统一 `task_runs / task_events` 主链 | `backend/services/story_engine_workflow_service.py` `backend/services/task_service.py` `backend/models/task_run.py` `backend/models/task_event.py` |
| `E2-02` | 大纲压力测试并轨到任务系统 | `已完成（第一版）` | `P2` | 让开书第一步也进入统一任务链，支持大纲生成、挑刺、裁决、落库的完整回放 | `backend/services/story_engine_workflow_service.py` `backend/api/v1/story_engine.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/app/dashboard/page.tsx` |
| `E2-03` | 初始化导入 / 模板导入并轨到任务系统 | `已完成（第一版）` | `P2` | 把上传大纲、模板导入、知识库批量初始化等开书动作并到统一任务链，结束项目初始化阶段的最后分叉 | `backend/api/v1/story_engine.py` `backend/services/story_engine_import_service.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/app/dashboard/page.tsx` |

### `P2-01` 验收标准

- 用户在桌面端未正式保存的正文，可以在手机端继续恢复。
- 云端暂存不替代正式章节保存，只服务跨设备接续。
- 当前章正式保存、回滚或重写后，对应云端暂存会同步清掉，避免旧稿反复覆盖。
- 写手前台仍然只看到“保稿 / 恢复 / 继续写”，不会暴露技术术语。

### `P2-02` 验收标准

- 写手能在工作台里看到最近一次正文生成、检查收口、设定补全的大致执行轨迹。
- 轨迹展示要写手可理解，不暴露模型路由、任务系统内部细节。
- Dashboard 能快速定位“哪本书最近在跑、卡在哪一步、刚完成了什么”。

### `P2-02` 当前进度

- 已完成（第一版）：后端已新增项目级 `/api/v1/projects/{project_id}/task-playback` 聚合接口，把最近任务与最近事件收成一份回放数据，前端不需要再自己拼多次请求。
- 已完成（第一版）：`story-room` 已加入统一“最近过程”区，会把当前页的正文生成 / 正文检查 / 终稿收口时间线，与项目级自动补设定回放合并展示成一条写手可读的过程线。
- 已完成（第一版）：Dashboard 的“最近任务”已收口成“最近发生了什么”，能更快看到哪本书刚跑完、正在处理中，或者停在了哪一步。
- 已完成（第一版）：配合后续 `E2-01`，这些回放入口现在已经能直接消费持久化的章节工作流，不再只依赖本次请求的瞬时返回。

### `E2-01` 验收标准

- `chapter-stream / realtime-guard / final-optimize` 都有可查询的统一任务记录。
- 服务级返回的时间线与 `task_runs / task_events` 中的持久化结果语义一致。
- 后续前台做轨迹回放时，不需要再只依赖一次性接口响应。

### `E2-01` 当前进度

- 已完成（第一版）：`realtime-guard / chapter-stream / final-optimize` 三条章节工作流现在都会写入统一 `task_runs / task_events`，并把 `workflow_timeline`、章节号、阶段状态、关键结果一起沉到任务结果里。
- 已完成（第一版）：`chapter-stream` 已改成边流式生成边落任务事件；`realtime-guard` 在正文流内部调用时会关闭独立持久化，避免每段正文都炸出一条单独检查任务。
- 已完成（第一版）：`story-room` 现在会把当前 `chapter_id` 透传到三个工作流，请求能稳定绑定真实章节；未正式落章时则自动退回项目级任务记录。
- 已完成（第一版）：Dashboard 与任务详情读取章节号时，已经支持从 `task.result.chapter_number` 回退，不会因为任务挂在项目级而丢失章号。
- 已完成（第一版）：`story-room` 与 Dashboard 都已经识别 `workflow_status=paused`，暂停态回放不会再被误显示成普通“已完成”。

### `E2-02` 验收标准

- `outline-stress-test` 有可查询的统一任务记录。
- 大纲初版生成、守护/节奏/逻辑校验、补丁轮、裁决和落库都能回放。
- 写手在 `story-room` 和 Dashboard 看到的“最近过程”不再只偏向正文阶段，开书阶段也完整可见。

### `E2-02` 当前进度

- 已完成（第一版）：`outline-stress-test` 现在也会写入统一 `task_runs / task_events`，开书阶段第一次真正进入项目级任务主链。
- 已完成（第一版）：时间线已经覆盖 `outline_stress_started / outline_blueprint_prepared / guardian_review / commercial_review / logic_review / debate_patch_applied / outline_arbitration / outline_persisted / outline_stress_completed`，不再只有最终返回结果。
- 已完成（第一版）：`story-room` 发起大纲压力测试后，会把 `workflow_timeline` 立即并入当前页最近过程，同时刷新项目级任务回放。
- 已完成（第一版）：Dashboard 最近任务区已经能识别 `story_engine.outline_stress_test`，并把动作入口直接导向大纲区，开书阶段不再是回放盲区。

### `E2-03` 验收标准

- `imports/bulk` 有可查询的统一任务记录。
- 模板导入、手工设定包导入、覆盖区块替换、后台策略套用都能回放。
- 写手在 `story-room` 和 Dashboard 看到的最近过程，已经覆盖“导入起盘设定”这一类项目初始化动作。

### `E2-03` 当前进度

- 已完成（第一版）：`story_engine/imports/bulk` 现在会写入统一 `task_runs / task_events`，并返回标准化 `workflow_timeline`，不再是同步导入后一次性黑盒返回。
- 已完成（第一版）：时间线已经覆盖 `bulk_import_started / bulk_import_preflight_checked / bulk_import_replace_scope_prepared / bulk_import_{section} / bulk_import_model_preset_applied / bulk_import_completed`，能回看整套初始化设定是怎么落进去的。
- 已完成（第一版）：`story-room` 导入设定成功后，会立刻把导入过程并入最近过程，并刷新项目任务回放；Dashboard 也已经能识别 `story_engine.bulk_import` 并跳回设定区。
- 已完成（第一版）：相关后端回归已经补到导入服务层，当前导入链和既有大纲/正文/终稿链一起通过了针对性测试与前端类型检查。

### `P2-01` 当前进度

- 已完成（第一版）：后端已补齐云端续写稿快照表、迁移、服务层和四个接口，支持按项目列出、读取当前章快照、按 scope 覆写、删除单条续写稿。
- 已完成（第一版）：`story-room` 已接入“本机保稿 + 云端续写”双层保护，联网时会自动续存，切章后能识别当前章是否存在可恢复的续写稿。
- 已完成（第一版）：正文区“写作保护”已加入写手可理解的续写提示，只暴露“恢复续写稿 / 清掉这份续写稿 / 换设备可续写”，没有暴露任务系统或技术术语。
- 已完成（第一版）：正式保存、版本回退、片段改写、终稿确认后都会主动清理当前章续写稿，避免旧草稿反复覆盖正式章节。

---

## 工程纯化项

这些项不是写手直接感知的功能，但会影响后续维护和扩展效率。

| ID | 任务 | 状态 | 优先级 | 说明 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `E1-01` | `items / factions` 底层领域模型原生化 | `已完成（第一版）` | `P1` | 公开 API 已对齐，运行时已改为原生优先，wrapper 只保留历史兼容读取/迁移 | `backend/services/project_service.py` `backend/models/story_engine.py` |
| `E1-02` | Story Bible 关联与溯源能力增强 | `已完成（第一版）` | `P1` | 工作区已能返回设定关联/来源摘要，并为后续双向定位提供稳定锚点 | `backend/services/story_engine_kb_service.py` `backend/services/story_engine_unified_knowledge_service.py` |
| `E1-03` | 章节工作流事件化与可观测性增强 | `已完成（第一版）` | `P2` | 主链能用，但事件与任务观测还可以更完整 | `backend/services/story_engine_workflow_service.py` |

### `E1-01` 当前进度

- 已完成（第一版）：`build_public_story_bible_sections()` 已调整为原生 `items / factions` 优先，兼容 wrapper 只作为历史兜底，不再反向覆盖原生条目。
- 已完成（第一版）：`get_owned_project(..., with_relations=True)` 现在会在读取时自动把项目级 `world_settings` wrapper 迁移到 `project_items / project_factions`，并清理旧 wrapper 行。
- 已完成（第一版）：分支 `Story Bible` 快照会在读取时被 canonical 化为原生 section delta，不再继续把 `item/faction` 混在 `world_settings` 里。
- 已完成（第一版）：回滚链路也会先做 snapshot canonical 化，避免旧版本恢复后把 branch payload 再次写回 legacy wrapper 形态。

### `E1-02` 当前进度

- 已完成（第一版）：`story-engine/workspace` 现在会额外返回 `knowledge_provenance`，为每条可见设定整理 `scope_origin / last_source_workflow / last_action / recent_chapters / inbound_relations / outbound_relations`。
- 已完成（第一版）：设定关联已经覆盖人物关系、伏笔挂钩、物品归属/地点、势力首领/成员/地盘、剧情线聚焦对象、时间线地点/人物状态等关键连续性链路。
- 已完成（第一版）：章节总结里“已应用的设定更新”会回写到对应实体的 provenance 上，后续做“从设定回跳最近影响章节”时不需要再重拆历史数据。
- 已完成（第一版）：统一保存/删除接口现在会返回 `entity_locator`，把 `section_key / entity_id / entity_key / label / branch_id` 一起带回，便于后续前端做稳定定位。

### `E1-03` 当前进度

- 已完成（第一版）：`chapter-stream` 的 `start / plan / chunk / guard / done` 事件现在都带统一 `workflow_event`，终止事件会附带完整 `workflow_timeline`，便于回放和失败定位。
- 已完成（第一版）：`realtime-guard` 现在会返回标准化时间线，明确区分“开始校验 / 守护结论 / 修法生成 / 裁决停写”四个阶段。
- 已完成（第一版）：`final-optimize` 现在会回传轮次级时间线，覆盖每轮守护、逻辑、节奏、文风、锚定、仲裁，以及 `kb_updates_normalized / chapter_summary_persisted / final_optimize_completed` 等落库节点。
- 已完成（第一版）：相关回归已补齐 `chapter stream / realtime guard / final optimize` 三条链，当前章节工作流的事件契约已经有稳定测试兜底。

---

## 暂不做

这些项当前明确不进入交付主线。

| ID | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| `N1-01` | 内容合规前台链路 | `暂不做` | 生成后由目标平台完成审核 |
| `N1-02` | 会员 / 充值 / 成长体系 | `暂不做` | 先把核心创作链路打扎实 |
| `N1-03` | B 端白标 / 平台管理后台 | `暂不做` | 当前优先服务普通写手主路径 |
| `N1-04` | 企业级监控告警平台 UI | `暂不做` | 工程可用即可，不进入当前前台交付 |

---

## 推荐实施顺序

按当前仓库状态，后续建议严格按下面顺序推进：

1. `P0-01` 新建书后的默认动作继续降噪
2. `P0-02` 新章进入正文区后的主按钮继续压缩
3. `P0-03` 终稿、章节总结、设定沉淀的复用出口收口
4. `P0-04` 设定与正文的双向定位
5. `P0-05` 主链手工 smoke 用例固化
6. `P1-01` 管理员模型路由 / 策略页
7. `P1-02` 实体生成并入统一任务链
8. `E1-01` `items / factions` 底层领域模型原生化
9. `E1-02` Story Bible 关联与溯源能力增强
10. `E1-03` 章节工作流事件化与可观测性增强
11. `P1-04` 独立风格中心
12. `P1-05` 移动端轻量化创作模式
13. `P2-01` 跨端云端续写草稿
14. `P2-02` 工作台任务轨迹与流程回放
15. `E2-01` 章节工作流持久化并轨到任务系统
16. `E2-02` 大纲压力测试并轨到任务系统
17. `E2-03` 初始化导入 / 模板导入并轨到任务系统

---

## 当前判断

如果只看“能不能用”，项目已经不只是能跑主链，而是已经把“开书初始化 -> 大纲 -> 正文 -> 终稿 -> 设定沉淀”这一整条核心路径的主要工作流都并到了统一任务回放里。

如果看“能不能作为真正稳定的写作产品持续使用”，当前任务表里的 `P0 / P1 / P2 / E1 / E2` 这一批已经基本完成第一轮收口。接下来更合理的动作不是脱表继续散改，而是先做两件事：

- 先按固定 smoke 清单，把“开书初始化 / 导入模板 / 测大纲漏洞 / 生成正文 / 终稿收口 / 下一章接续”整链再做一轮系统回归
- 再补下一版任务表，把后续要做的体验精修、工程纯化或运维能力明确编号后继续推进

按当前任务表，现有明确列出的“必须先做 / 可以后做 / 下一阶段任务”已经全部推进到 `已完成（第一版）` 或 `暂不做`。如果后面继续新增开发项，应该先回写这份表，再开始下一轮实现。

---

## 第二版实施任务表（当前有效）

这部分是从现在开始继续开发时要遵守的新顺序。

第一版已经把核心主链打通，第二版不再重开新流程，而是集中解决四类问题：

- 把“人工 smoke 可用”升级为“可重复执行的自动化回归”
- 把“能看到最近过程”升级为“实时过程可推送、失败后可恢复”
- 把“单工作台主链能跑”升级为“长时间使用也稳定、不拖、不乱”
- 把“工程上能工作”升级为“可维护、可观察、可上线”

### 第二版固定边界

- 写手前台仍然只保留 `创建项目 -> 大纲 -> 正文 -> 终稿 -> 设定 -> 下一章` 这一条主路径。
- 第二版不引入新前台体系，不把管理员配置、模型组合、底层辩论机制暴露给写手。
- 第二版优先做“稳、顺、可回放、可恢复”，不是优先堆更多按钮和页面。
- 所有新任务依然优先收口在 `dashboard / story-room`，不让旧页面重新成为主入口。

### 第二版里程碑

| 里程碑 | 状态 | 说明 |
| --- | --- | --- |
| 自动化回归落地 | `待开始` | 把现在的人工 smoke 清单沉成可执行脚本和固定入口 |
| 实时任务过程升级 | `待开始` | 把轮询式过程查看升级成更即时的任务推送和跨页同步 |
| 长流程稳定性升级 | `待开始` | 让大纲、导入、终稿这类长流程能失败恢复、重试和继续看 |
| 工作台性能纯化 | `待开始` | 把 `story-room` 的大工作区做按阶段分层加载和缓存收口 |

### 第二版必须先做

| ID | 任务 | 状态 | 优先级 | 目标 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `P3-01` | 主链自动化回归落地 | `待开始` | `P0` | 把现有人工 smoke 清单沉成固定命令、固定数据和固定断言，后续每次改主链都能直接跑 | `docs/architecture/current-priority-checklist.md` `backend/scripts/story_engine_live_smoke.py` `frontend/package.json` `backend/tests` |
| `P3-02` | 工作台最近过程实时推送 | `待开始` | `P0` | 让 `story-room` 和 Dashboard 不再主要靠轮询刷新，而是更即时地看到“刚发生了什么 / 卡在哪一步” | `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/app/dashboard/page.tsx` `backend/api/ws.py` `backend/realtime/task_events.py` |
| `P3-03` | 长流程失败恢复与重试收口 | `待开始` | `P0` | 让导入设定、测大纲漏洞、终稿收口等长流程在失败/中断后可恢复、可重试、可继续查看结果 | `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `backend/services/story_engine_import_service.py` `backend/services/story_engine_workflow_service.py` `backend/services/task_service.py` |
| `P3-04` | `story-room` 首屏减载与按阶段懒加载 | `待开始` | `P0` | 把大工作台改成按阶段拉取和缓存，减少首次进入、切章、切分线时的等待和卡顿 | `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `backend/api/v1/story_engine.py` `backend/services/story_engine_kb_service.py` `backend/services/task_service.py` |

### 第二版可以后做

| ID | 任务 | 状态 | 优先级 | 说明 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `P4-01` | 跨项目风格 / 模板资产库 | `待开始` | `P1` | 把用户常用的文风底稿、起盘模板、章节手感沉成个人资产，而不只停留在当前项目里 | `frontend/app/dashboard/preferences/page.tsx` `backend/api/v1/profile.py` `backend/services/preference_service.py` |
| `P4-02` | 协作写作的章节锁与冲突提醒 | `待开始` | `P1` | 让多人协作从“能加成员”提升到“谁在改哪一章、会不会互相覆盖”可感知 | `frontend/app/dashboard/projects/[projectId]/collaborators/page.tsx` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `backend/services/project_service.py` `backend/api/v1/projects.py` |
| `P4-03` | 导出 / 交付中心 | `待开始` | `P1` | 把项目导出从零散按钮收成统一出口，补齐整书导出、分卷导出、终稿包导出等常用动作 | `frontend/app/dashboard/page.tsx` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `backend/services/export_service.py` `backend/api/v1/projects.py` |

### 第二版工程纯化项

| ID | 任务 | 状态 | 优先级 | 说明 | 关键文件 |
| --- | --- | --- | --- | --- | --- |
| `E3-01` | Story Engine 长流程异步任务化 | `待开始` | `P1` | 把大纲压力测试、批量导入、终稿收口从同步请求进一步收口到后台任务派发，减少超时和前台阻塞 | `backend/tasks/celery_app.py` `backend/services/story_engine_workflow_service.py` `backend/services/story_engine_import_service.py` `backend/api/v1/story_engine.py` |
| `E3-02` | 任务事件订阅层统一 | `待开始` | `P1` | 把已有 `task_events`、WebSocket、前台轮询入口统一成一套更稳定的订阅层，减少页面各自拼装 | `backend/realtime/task_events.py` `backend/api/ws.py` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` `frontend/app/dashboard/page.tsx` |
| `E3-03` | `story-room workspace` 契约拆分与缓存 | `待开始` | `P1` | 把现在偏大的 workspace 读法拆成主数据 + 分阶段数据 + 轻量缓存，减少重复拉全量 | `backend/api/v1/story_engine.py` `backend/services/story_engine_kb_service.py` `frontend/types/api.ts` `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx` |
| `E3-04` | 自动化 smoke 数据夹具与脚本统一 | `待开始` | `P1` | 把手工 smoke、后端 live smoke、前端测试入口统一命名、统一命令、统一测试账号策略 | `backend/scripts/story_engine_live_smoke.py` `backend/tests` `frontend/package.json` `docs/architecture/current-priority-checklist.md` |

### 第二版暂不做

第二版继续沿用第一版的暂不做边界，额外补一条：

- 不做写手前台的“高级设置中心”扩张；所有高复杂度控制继续收口在后台管理员能力里。

### 第二版推荐实施顺序

从现在开始，后续建议严格按下面顺序推进：

1. `P3-01` 主链自动化回归落地
2. `E3-04` 自动化 smoke 数据夹具与脚本统一
3. `E3-01` Story Engine 长流程异步任务化
4. `E3-02` 任务事件订阅层统一
5. `P3-02` 工作台最近过程实时推送
6. `P3-03` 长流程失败恢复与重试收口
7. `E3-03` `story-room workspace` 契约拆分与缓存
8. `P3-04` `story-room` 首屏减载与按阶段懒加载
9. `P4-01` 跨项目风格 / 模板资产库
10. `P4-02` 协作写作的章节锁与冲突提醒
11. `P4-03` 导出 / 交付中心

### 第二版当前判断

当前最合理的下一步不是继续往产品里加新按钮，而是先把“已经能用”的主链变成“每次改完都能快速验证、长流程断了也能接着跑、工作台过程更实时”的稳定版本。

所以第二版的第一个实际执行点应该是：

- 先完成 `P3-01`，把主链自动化回归固定下来
- 然后立刻补 `E3-04`，把 smoke 的脚本、数据夹具和命令入口统一

只有这两步先落地，后面继续改实时推送、异步任务化和性能分层时，回归成本才不会持续抬高。
