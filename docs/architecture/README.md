# 项目架构索引

这组文档不是产品介绍，而是基于当前代码实现整理出来的架构入口。
它回答三个问题：

1. 这个项目的核心领域模型是什么
2. 章节生成和修订到底是怎么跑起来的
3. `story-room`、旧章节链和后端 API 现在到底是如何对接的

## 建议阅读顺序

1. `implementation-task-table.md`
2. `domain-model.md`
3. `chapter-lifecycle.md`
4. `agent-collaboration.md`
5. `api-contract-map.md`
6. `legacy-chapter-endpoint-offboarding.md`
7. `alignment-backlog.md`

## 一张总图

```text
                       User
                        |
        +---------------+----------------+
        |                                |
   explicit preference              collaboration role
        |                                |
  UserPreference                  Project / ProjectCollaborator
        |                                |
        +----------------+---------------+
                         |
                    Story Bible
                         |
         +---------------+----------------+
         |                                |
   project base canon             branch override snapshot
         |                                |
  Character / Location / ...      ProjectBranchStoryBible
         |                                |
         +---------------+----------------+
                         |
                    runtime context
                         |
                 generation pipeline
                         |
 Librarian -> Architect -> Writer -> CanonGuardian -> Critic
                         |                           |
                         +------ Debate -> Editor ---+
                                      |
                                   Approver
                                      |
                                  Chapter
                                      |
          +-------------+-------------+-------------+
          |             |                           |
    ChapterVersion   Evaluation                 Review artifacts
                                              comment / decision /
                                                  checkpoint
                                      |
                                  final gate
                                      |
                           task state + websocket updates
```

## 这套系统最重要的三个判断

- 它本质上是一个“长篇小说生产工作流系统”，不是一个简单的文本生成器。
- `Story Bible` 在代码里是事实源，不是附属资料；`Chapter` 在代码里是流程单元，不是纯文本。
- 写手主入口已经收口到 `story-room`，而模型路由、角色分工和预设策略属于后台系统层，不属于前台产品层。

## 每份文档分别回答什么

### `domain-model.md`

重点回答：

- 为什么项目要同时有项目级 Story Bible 和分支级 Story Bible 快照
- 为什么章节要有版本、评估快照、评论、评审决议、检查点
- 为什么 Story Bible 变更会让章节评估失效

### `chapter-lifecycle.md`

重点回答：

- 章节为什么在代码里更像工作流工单而不是纯文本
- `final` 为什么不是最终真相，`final_gate_status` 才是
- stale review、stale checkpoint、stale evaluation 是怎么形成的
- 为什么改动 Story Bible 会影响章节放行

### `agent-collaboration.md`

重点回答：

- 章节生成为什么不是单次 prompt
- coordinator 到底在控制什么
- truth layer 为什么是修订回路的核心
- 模型不可用时为什么系统还能跑

### `api-contract-map.md`

重点回答：

- 每个前端页面实际依赖哪些接口
- 后端服务真正承诺了什么数据结构
- 当前最明显的前后端契约偏差在哪里

### `legacy-chapter-endpoint-offboarding.md`

重点回答：

- 旧 `/api/v1/chapters/*` 兼容入口现在还剩哪些
- 哪些端点可以先下线，哪些要等工作流语义迁移后再下线
- 如何通过 `legacy_chapter_endpoint_used` 观测日志判断下线时机

### `alignment-backlog.md`

重点回答：

- 当前哪些偏差会直接影响联调和功能可用性
- 哪些偏差属于“语义和实现不一致”
- 如果要开始收口，修复顺序应该是什么

### `implementation-task-table.md`

重点回答：

- 当前哪些任务已经完成
- 哪些任务正在做、接下来按什么顺序做
- 每项任务对应哪些关键文件和验收标准

## 当前最值得优先关注的偏差

- `items` / `factions` 的主存储语义已经原生化，Story Bible 的第一版关联/溯源摘要也已补齐。
- 实体生成已经并入项目级 task/event 主链，章节工作流本身的第一版事件链也已补齐，接下来更值得盯的是 `story-room` 与旧章节编辑器的进一步并轨。
- `story-room` 已经接入正式章节主链，但完整 review/comment/checkpoint 操作仍主要保留在专用章节编辑器中。

## 推荐用法

- 想理解“数据为什么这样建模”，先看 `domain-model.md`
- 想理解“章节从 draft 到 final 中间到底经历什么”，看 `chapter-lifecycle.md`
- 想理解“章节生成为什么会经过这么多环节”，看 `agent-collaboration.md`
- 想做联调、修页面、补接口，对照 `api-contract-map.md`
- 想开始系统化收口当前偏差，看 `alignment-backlog.md`
- 想看当前书架该先处理哪本、最近写作势头怎么样，直接看 Dashboard 总览实现：它已经补入活动快照、质量快照、任务健康和焦点队列。
