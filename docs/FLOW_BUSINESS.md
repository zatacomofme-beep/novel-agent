# Novel Agent — 业务流图

> 描述用户从零开始使用本系统，经历的全部业务流程、阶段、角色分工与产出。
> 包含：引导流程、主创作流程、审阅发布流程，以及新增的声音指纹建立流程。

---

## 一、用户旅程总览

```
阶段一：启动         阶段二：规划              阶段三：创作              阶段四：审阅
─────────────        ──────────────            ──────────────            ──────────────

[注册/登录]
       │
       ▼
[想法输入] ──→ [引导式世界观构建] ──→ [大纲确认] ──→ [章节生成] ──→ [审阅循环] ──→ [发布]
       │                                      │              │
       │                                      │              ├── 通过 → 发布
       │                                      │              ├── 修改 → 返回创作
       │                                      │              └── 拒绝 → 返回大纲
       │                                      │
       │                              [写作样章]（可选）
       │                                      │
       └──────────────────────────────────────┘
              声音指纹建立（提升风格一致性）
```

---

## 二、阶段一：引导式世界观构建

### 2.1 业务流程

```
用户输入：一句话想法（例："我想写一个修仙世界，主角从废物流崛起"）
        │
        ▼
系统通过 Gemini 3.1 Pro 执行 8 步引导对话：

Step 1: 世界类型
        "你想要构建的世界是什么类型？"
        → 用户选择：东方修炼 / 西方奇幻 / 科幻 / 现实 / 其他

Step 2: 力量体系
        "世界中的力量来源是什么？"
        → 用户填写或选择

Step 3: 社会结构
        "这个世界的主要社会形态是？"
        → 用户填写

Step 4: 主要冲突
        "故事的核心冲突是什么？"
        → 用户填写

Step 5: 道德复杂性
        "正派一定有道德优势吗？"
        → 用户选择：纯粹正义 / 灰色道德 / 复杂博弈

Step 6: 故事基调
        "整体基调偏向？"
        → 用户选择：黑暗 / 希望 / 讽刺 / 史诗 / 其他

Step 7: 结局预设
        "你希望故事的结局偏向？"
        → 用户选择：完满 / 悲剧 / 开放 / 讽刺性

Step 8: 特殊设定
        "有没有需要特别设定的重要规则？"
        → 用户填写

        ▼
生成 StoryBible 草稿
（角色、势力、地点、力量体系、核心冲突、主题等）
        │
        ▼
用户可以在 World-Building 界面中编辑确认
        │
        ▼
Project 状态：SETUP_COMPLETE
```

### 2.2 产出

| 产出 | 存储位置 |
|-----|---------|
| Project.id | PostgreSQL |
| StoryBible（世界观） | PostgreSQL (StoryBibleVersion) |
| Character（初始角色列表） | PostgreSQL |
| Location（主要地点） | PostgreSQL |
| Faction（势力） | PostgreSQL |
| PlotThread（核心冲突线） | PostgreSQL |

---

## 三、阶段二：大纲确认（Architect 协作）

### 3.1 业务流程

```
用户确认 StoryBible 后
        │
        ▼
StoryEngineWorkflowService.run_outline_workflow(project_id)
        │
        ├─→ ArchitectAgent
        │     输入：StoryBible + 用户引导记录
        │     输出：Blueprint（大型章纲）
        │           chapters: [
        │             { chapter_num, title, summary, plot_threads, characters, tone, tension_target }
        │           ]
        │
        ▼
用户审阅 Blueprint
        │
        ├─ 确认 → 进入章节创作阶段
        │
        └─ 修改 → 触发 Architect 重新生成 / 用户手动编辑大纲
```

### 3.2 Blueprint 大纲格式

```
{
  "total_chapters": 30,
  "arc_structure": "三幕结构",
  "chapters": [
    {
      "chapter_num": 1,
      "title": "废物",
      "summary": "主角在家族测试中被判定为废物，受到同族冷遇...",
      "plot_threads": ["main_line", "spiritual_root"],
      "characters": ["主角", "配角A"],
      "tone": "压抑、积蓄",
      "tension_target": 0.2,
    },
    ...
  ]
}
```

---

## 四、阶段三：章节创作（含新增模块）

### 4.1 业务流程

```
用户选择章节目录中的某章，点击「生成」
        │
        ▼
GenerationService.run(chapter_id, user_id)
        │
        ├─→ [数据准备] ContextBuilder + Neo4j + SocialTopology + Foreshadowing
        │
        ├─→ [声音指纹] 若用户上传过样章：
        │     从 UserPreference 读取 StyleFingerprint
        │     voice_description 注入 Writer system_prompt
        │
        ├─→ [Architect] 细化本章 outline
        │
        ├─→ [Writer] 4段生成（开篇/发展/高潮/收尾）
        │     每段生成后自动 save_checkpoint()
        │     若中途断线，可从 checkpoint 恢复
        │
        ├─→ [BetaReader] 并行评估
        │     四维反馈：tension + rhythm + voice + engagement
        │     产出：beta_feedback（含节奏偏差报告）
        │
        ├─→ [CanonGuardian] 典律检查
        │     若 blocking_issues > 0 → 流程终止
        │
        ├─→ [Revision Loop]（最多3轮）
        │     Critic → Debate → Editor（注入 beta_feedback）
        │
        ├─→ [Approver] 最终审批
        │
        └─→ [后处理]
              L2EpisodicMemory.save_episode()
              Neo4jService.create_event_node()
              ForeshadowingLifecycleService.scan_and_plant()
              SemanticCompressionService.compress_if_needed()

        ▼
生成完成，内容写入 Chapter.content
状态更新：DRAFT → REVIEW_PENDING
```

### 4.2 断点续传流程

```
场景：Writer 生成到第3段时断线
        │
        ▼
用户重新点击「继续生成」
        │
        ├─→ CheckpointService 检测到已有 checkpoint
        │     last_checkpoint = { segments_completed: 2, segment_3_partial: "..." }
        │
        ├─→ Writer 只需生成第3段和第4段
        │     segments_to_generate = [3, 4]
        │
        └─→ 完成后，拼接所有段落，恢复完整章节
```

### 4.3 声音指纹建立（独立于章节创作）

```
用户进入「风格配置」页面
        │
        ▼
用户粘贴 3-5 章自己的写作样章（可以是已完成的其他小说）
        │
        ▼
StyleFingerprintService.build(samples)
        │
        ├─ 提取句式节奏、POV特征、语言密度、对话风格
        ├─ 生成 voice_description
        │
        ▼
指纹存入 UserPreference
        │
        ▼
后续所有章节生成时，voice_description 自动注入 Writer prompt
BetaReader 自动进行 voice_alignment 检查
```

---

## 五、阶段四：审阅循环与发布

### 5.1 业务流程

```
章节生成完成，状态：REVIEW_PENDING
        │
        ▼
用户或系统触发审阅流程
        │
        ├─→ BetaReaderAgent（系统自动）
        │     产出：beta_feedback（读者视角反馈）
        │
        ├─→ CriticAgent（系统自动）
        │     产出：review（技术质量评审）
        │
        └─→ CanonGuardianAgent（系统自动）
              产出：canon_report（典律一致性）

        ▼
审阅结论汇总
        │
        ├─ [approval == true AND canon_blocking == 0]
        │     状态 → APPROVED
        │     用户可手动发布
        │
        ├─ [canon_blocking > 0]
        │     状态 → CANON_CONFLICT
        │     触发 World-Building 冲突修复流程
        │
        └─ [approval == false OR issues > threshold]
              状态 → NEEDS_REVISION
              用户可：
              ├─ 手动修改章节内容
              ├─ 重新生成（基于当前 outline）
              └─ 调整 story_bible 后重新生成
```

### 5.2 审阅结果分支

```
                    ┌──────────────────────────────┐
                    │   CanonGuardian               │
                    │   blocking_issues = 0         │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │   Approver                   │
                    │   approved = true            │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │           发布（PUBLISHED）               │
              └───────────────────────────────────────────┘

                    ┌──────────────────────────────┐
                    │   CanonGuardian               │
                    │   blocking_issues > 0         │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │       World-Building 冲突修复            │
              │  用户修复冲突 → 重新生成章节              │
              └───────────────────────────────────────────┘

                    ┌──────────────────────────────┐
                    │   Approver                   │
                    │   approved = false           │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │       Revision / 手动修改               │
              │  修改后重新提交审阅                       │
              └───────────────────────────────────────────┘
```

---

## 六、副线流程

### 6.1 世界观迭代（创作过程中编辑 Story Bible）

```
用户在任何阶段进入 World-Building 界面
        │
        ├─→ 编辑角色属性
        ├─→ 添加/修改地点
        ├─→ 新增势力
        ├─→ 更新力量体系
        └─→ 修改核心冲突

        ▼
StoryBibleVersionService.create_new_version(project_id, changes)
        │
        ├─→ 已有章节 → 触发 CanonGuardian 冲突检测
        │     ├─ 无冲突 → 正常更新
        │     └─ 有冲突 → 标记受影响章节，提示用户审阅
        │
        └─→ 新生成章节 → 直接使用新版 Story Bible
```

### 6.2 分支管理

```
用户创建分支（Branch）
        │
        ├─→ Branch A（主分支，主线剧情）
        └─→ Branch B（探索分支A，用户选择不同走向）

        ▼
各分支独立生成章节，独立维护：
        ├─ Chapter（各自独立 chapter_number）
        ├─ StoryBible（共享基础，分支独立修改）
        └─ Foreshadowing（各自独立追踪）

        ▼
用户可合并分支（Merge）
        ├─→ 冲突检测：相同章节号的内容冲突
        └─→ 用户手动解决冲突后合并
```

### 6.3 一键分发（已移除，不在当前计划）

---

## 七、用户权限与角色

| 角色 | 权限范围 |
|-----|---------|
| **Owner** | 全部权限（项目设置、删除、发布） |
| **Collaborator** | 创作、审阅、编辑（不能删除项目） |
| **Viewer** | 只读（查看章节、审阅反馈） |

---

## 八、核心业务指标（成功标准）

| 指标 | 定义 | 目标值 |
|-----|------|-------|
| 章节通过率 | Approver.approved == true 的章节比例 | > 80% |
| 无需 Revision 率 | 1轮生成即通过 Approver 的比例 | > 50% |
| 典律冲突率 | CanonGuardian blocking_issues > 0 的比例 | < 10% |
| 平均生成成本 | 每章 LLM token 消耗（折算美元） | < $1.5 |
| 声音一致性 | BetaReader voice_alignment 得分 | > 0.85 |
| 节奏合规率 | SceneRhythm deviation 段落占总段落比例 | < 15% |
| 伏笔解决率 | 已 RESOLVED 的伏笔 / 总伏笔 | > 70% |
