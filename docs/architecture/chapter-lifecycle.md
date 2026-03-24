# Chapter 生命周期与最终门禁

这份文档专门解释 `Chapter` 在项目里的真实地位。

在当前代码里，章节不是一段文本，而是一个带状态、版本、评估、审校、检查点和最终放行规则的流程对象。

主要依据：

- `backend/models/chapter.py`
- `backend/services/chapter_service.py`
- `backend/services/review_service.py`
- `backend/services/evaluation_service.py`
- `backend/services/chapter_gate_service.py`
- `backend/services/project_service.py`

## 1. 章节在系统中的位置

```text
Project + Branch + Volume
          |
        Chapter
          |
   +------+------+------+------+
   |             |             |
 version     evaluation     review artifacts
 history      snapshot      comment/decision/checkpoint
          |
      final gate
          |
     status transition
```

所以一个章节同时承担四种职责：

- 文本容器
- 版本容器
- 评估结果容器
- 工作流状态容器

## 2. 创建章节时发生什么

`create_chapter()` 做的事情不是简单插一条 chapter。

它会同时做这些事：

1. 校验项目和权限
2. 解析 branch/volume 作用域
3. 检查章节号冲突
4. 创建 `Chapter`
5. 立即创建 `ChapterVersion(version_number=1)`
6. 记录偏好学习 observation
7. 附加当前门禁元数据

这意味着章节从诞生开始就是一个“版本化工作项”。

## 3. 更新章节时发生什么

`update_chapter()` 的核心逻辑是：

- 允许更新标题、内容、提纲、状态、质量快照、branch、volume
- 如果内容变更，会递增 `current_version_number`
- 如果 `create_version=True`，会追加一条新的 `ChapterVersion`
- 如果内容、标题或分支作用域发生变化，已有评估会被标记 stale
- 如果章节原本已经是 `final`，但内容又发生变化，在未显式指定状态时会自动降级回 `review`

这说明系统不允许“final 文稿被静默修改”。
任何实质改动都会回到审校流里。

## 4. 章节状态不是唯一真相

代码里有一个很重要的事实：

`chapter.status` 不是章节是否真的能发布的唯一判断标准。

真正的放行结果来自 `ChapterGateSummary`。

也就是说：

- `status=final` 是目标状态
- `final_ready` 和 `final_gate_status` 才是放行判断

这就是为什么系统会给章节附带这些派生字段：

- `review_gate_blocked`
- `evaluation_gate_blocked`
- `integrity_gate_blocked`
- `canon_gate_blocked`
- `final_ready`
- `final_gate_status`
- `final_gate_reason`

## 5. final gate 实际检查什么

`summarize_chapter_gate()` 的检查顺序大致可以理解为：

1. 有没有 `rejected` checkpoint
2. 有没有 `pending` checkpoint
3. review 是否缺失、被阻塞、或已经 stale
4. evaluation 是否缺失或 stale
5. Story Bible integrity 是否有 blocking issue
6. canon 是否有 blocking issue
7. 全部通过才进入 `ready`

也就是说，章节要进入最终放行，不只是“文本还不错”。
它必须同时满足：

- 审校流程完成
- 评估结果是新鲜的
- Story Bible 基座没有阻断问题
- 章节本身没有违背 canon

## 6. stale 在这里是核心概念

这个项目非常依赖 `stale` 概念。
代码里至少有三种典型的 stale：

### review stale

如果最新 review 针对的是旧版本号，而章节已经产生了更新版本，那么 review 失效。

### checkpoint stale

如果 checkpoint 针对的是旧版本号，而章节已经更新，那么 checkpoint 也失效。

### evaluation stale

以下情况会导致 evaluation stale：

- 章节内容变化
- 标题变化
- 章节被切到另一个 branch
- Story Bible 发生变化

这套设计的意义很大：

它防止系统继续拿“旧事实、旧文本、旧评审”当作当前真相。

## 7. 为什么 Story Bible 变化会影响章节

`replace_story_bible()` 在项目级或分支级 Story Bible 更新后，会调用 `_invalidate_story_bible_related_chapter_evaluations()`。

这意味着系统默认承认一个事实：

章节质量不是脱离世界设定独立存在的。

如果事实源更新了，那么之前基于旧事实源得到的评估和 gate 判断都可能不再可靠。

这也是这个项目比普通文本编辑器更“流程化”的原因。

## 8. review/checkpoint 为什么都绑定版本号

评论、评审决议、检查点都保存 `chapter_version_number`。

这带来两个结果：

- 你永远知道这条反馈是针对哪一版文本产生的
- 系统可以客观判断这条反馈是否已经过期

这比只记录“某章节上的评论”更成熟，因为它能支持真正的版本化审校。

## 9. 生成任务如何进入生命周期

当章节走生成链时：

1. coordinator 产出正文和提纲
2. `run_generation_pipeline()` 调用 `update_chapter(... create_version=True)`
3. 状态通常会进入 `review`
4. 随后立刻跑 `evaluate_existing_chapter()`
5. `quality_metrics` 被刷新

所以 AI 生成出来的章节并不会直接成为终态，而是进入后续门禁流。

## 10. 一个章节的典型路径

```text
draft
  -> writing
  -> review
  -> review + checkpoint + evaluation fresh
  -> integrity/canon all pass
  -> final

如果中途发生以下情况：
- 内容修改
- 标题修改
- branch 变化
- Story Bible 更新

就会触发部分 gate 失效，章节重新回到需要复核的状态
```

## 11. 这套生命周期设计想解决什么

它想解决的不是“能不能写出一章”。

它想解决的是：

- 一章是谁在什么事实基线下写出来的
- 这章对应的是哪一版文本
- 哪些评审和检查点还有效
- 这章现在是否真的满足放行条件

所以 `Chapter` 在这个项目里，本质上更接近：

`可追踪、可复核、可放行判断的创作工单`

而不是简单的 `chapter.content`。
