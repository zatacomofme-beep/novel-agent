# Novel Agent — 数据流图

> 描述数据在各模块之间的产生、传递、存储、消费的完整路径。
> 含新增的 StyleFingerprint 和 SceneRhythm 模块。

---

## 一、全局数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户输入层                                       │
│  ① 项目想法（一句话）  ② 引导式世界观  ③ 大纲确认  ④ 写作样章（声音指纹用）    │
│  ⑤ 章节审阅反馈       ⑥ 风格偏好配置  ⑦ 世界观编辑                          │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API / Task 入口层                                  │
│  POST /projects                 → ProjectService                            │
│  POST /projects/{id}/outline   → StoryEngineWorkflowService               │
│  POST /chapters/{id}/generate  → GenerationService (Celery task)          │
│  POST /style-fingerprint/build  → StyleFingerprintService                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL      │  │   Redis Cache    │  │   Qdrant          │
│  (结构化数据)      │  │  (会话/缓存)      │  │  (向量检索)        │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼                     ▼                     ▼
  Project / Chapter      Prompt Cache             Vector Store
  Character / Location  Token Budget            (story_bible /
  OpenThread / Foreshadow  Task State           characters /
  StoryBible / Episode  Rate Limit             foreshadowing)
  Evaluation / Tension                            │
  SocialTopology /                                ▼
  StyleFingerprint                          SemanticCompression
  (新增)                                     Service (长篇)
  SceneRhythmBaseline
  (新增)
```

---

## 二、StyleFingerprint 数据流（新增模块）

```
用户粘贴 3-5 章写作样章
        │
        ▼
StyleFingerprintService.build(samples)
        │
        ├─→ analyze_sentence_structure()  ──→ sentence_rhythm:
        │                                      avg_len: float       (平均句长)
        │                                      variance: float      (句长方差)
        │                                      type_distribution:   (陈述/疑问/感叹比例)
        │
        ├─→ analyze_pov_markers()  ──→ pov_signature:
        │                                indirect_discourse_ratio: float  (自由间接话语比例)
        │                                inner_monologue_density: float
        │
        ├─→ analyze_language_density()  ──→ language_density:
        │                                    adj_per_1000: float  (每千字形容词数)
        │                                    adv_per_1000: float  (每千字副词数)
        │                                    verb_strength: float   (动词强度)
        │
        ├─→ analyze_dialogue_patterns()  ──→ dialogue_style:
        │                                    dialogue_ratio: float  (对话占总字数比)
        │                                    tag_frequency: str    (high/medium/low)
        │                                    speech_verb_variety: float
        │
        └─→ generate_voice_description()  ──→ voice_description: str
                                             例："克制、听觉优先、碎片化、动作驱动"
        │
        ▼
UserPreferenceService.save_style_fingerprint(user_id, fingerprint)
        │
        ▼
StyleFingerprint 模型持久化
        │
        ├─→ 用途①：GenerationService → WriterAgent.system_prompt
        │        voice_description 注入 prompt
        │
        └─→ 用途②：BetaReaderAgent
                对比生成内容的声音特征与指纹，给出「声音漂移」警告
```

---

## 三、SceneRhythm 数据流（新增模块）

```
WriterAgent 生成章节 content
        │
        ▼
SceneRhythmService.segment(content)
        │
        ▼ 每 500-1000 字一分段
scenes: list[SceneSegment]
        │
        ▼ 并行两个分析
        │
        ├──────────────────────────┐
        ▼                          ▼
SceneRhythmService            TensionSensorService
.compute_tension_curve()       .analyze(content)
        │                              │
        ▼                              ▼
tension_curve: list[float]  tension_score: float
                               tension_level: "high"/"medium"/"low"
           ┌───────────────────────┴──────────────┐
           ▼                                      ▼
SceneRhythmService                          BetaReaderAgent
.compare_with_baseline()                   (tension_data 参数)
        │                                        │
        ▼                                        ▼
rhythm_deviation_report: {               beta_feedback.tension_data
  curve_shape: "mountain"|                   = {tension_score,
    "valley"|"flat"|"chaotic",                 tension_level,
  deviations: [                                  rhythm_alignment: ... }
    { scene_idx: int,                              │
      type: "too_slow"|"too_fast"|  }
      "abrupt_transition",               }
      suggestion: str
  ]
}
        │
        ▼
BetaReaderAgent（节奏维度）
  结合 voice + rhythm + tension
  给出综合反馈 → revision_plan
```

---

## 四、Generation Pipeline 完整数据流

```
run_generation_pipeline(chapter_id, user_id)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 第一步：数据准备（全部串行）                                         │
└─────────────────────────────────────────────────────────────────┘
        │
        ├─→ load_story_bible_context()         → story_bible (L3)
        │  ┌─→ vector_store.search() ──→ context_bundle (L1/L2)
        │  └─→ L2EpisodicMemory.get_recent_episodes() → episode_dicts
        │
        ├─→ SocialTopologyService.build_social_topology() → social_topology  [新增]
        │
        ├─→ ForeshadowingLifecycleService.get_active_threads() → open_threads
        │
        ├─→ CheckpointService.get_latest_generation_checkpoint() → resume_from?
        │
        ├─→ Neo4jService.query_causal_paths() → causal_context.chapters_paths  [新增]
        │
        └─→ Neo4jService.compute_character_influence() → causal_context.influence  [新增]
        │
        ▼
base_payload = {
  story_bible, context_brief, context_bundle,
  social_topology,     ← 新增
  causal_context,      ← 新增
  open_threads, resume_from, save_checkpoint, ...
}
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 第二步：Coordinator Agent 执行流程                                    │
└─────────────────────────────────────────────────────────────────┘
        │
        ├─ 1 LibrarianAgent ──→ context_brief + context_bundle
        │
        ├─ 2 ArchitectAgent ──→ chapter_plan
        │
        ├─ 3 WriterAgent
        │     注入: voice_description (StyleFingerprint) + causal_context (Neo4j)
        │     4段生成，每段 save_checkpoint()
        │     ──→ content
        │
        ├─ 4 BetaReaderAgent
        │     输入: content + tension_data + beta_history
        │         + persona_archetype + chapter_number + social_topology
        │     ──→ beta_feedback (含 rhythm_deviation)
        │
        ├─ 5 CanonGuardianAgent ──→ pre_canon_report
        │     若 blocking_issues > 0 → 直接返回（跳过 revision loop）
        │
        ├─ 6 _run_revision_loop()
        │     循环 rounds 1..max_rounds:
        │       CanonGuardian → canon_report
        │       Critic → review
        │       Debate → revision_plan
        │       Editor ← beta_feedback 注入（新增）
        │       满足退出条件 → break
        │
        └─ 7 ApproverAgent ──→ approval
        │
        ▼
response = { content, outline, beta_feedback, revision_plans,
             canon_report, truth_layer_context, approval, ... }
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 第三步：后处理（全部串行）                                          │
└─────────────────────────────────────────────────────────────────┘
        │
        ├─→ update_chapter(content, outline)
        │
        ├─→ L2EpisodicMemory.save_episode()  [新增：写章节摘要到 PostgreSQL]
        │
        ├─→ Neo4jService.create_event_node()  [新增：写 chapter_event 到因果图谱]
        │
        ├─→ ForeshadowingLifecycleService.scan_and_plant()
        │
        ├─→ SemanticCompressionService.compress_if_needed()
        │      (20+章时，按叙事弧压缩早期章节，降低 importance_score)
        │
        ├─→ evaluate_existing_chapter() → report
        │
        └─→ return pipeline_result
```

---

## 五、数据存储对应关系

| 数据类型 | 存储位置 | 生命周期 |
|---------|---------|---------|
| 项目/章节/角色等业务数据 | PostgreSQL | 持久化 |
| Prompt 缓存结果 | Redis | TTL 24h |
| 向量检索上下文 | Qdrant | 持久化，随项目删除 |
| 用户风格偏好 | PostgreSQL (UserPreference) | 持久化 |
| **StyleFingerprint** | PostgreSQL (新增表) | 持久化 |
| **SceneRhythmBaseline** | PostgreSQL (新增表) | 持久化 |
| **ChapterEpisode** (L2记忆) | PostgreSQL | 持久化 |
| 章节张力记录 | PostgreSQL (TensionSensor) | 持久化 |
| 角色关系图谱 | PostgreSQL + Neo4j | 持久化，双写 |
| 因果事件节点 | Neo4j | 持久化 |
| Celery 任务状态 | Redis | 任务结束后清除 |
| Rate limit 计数 | Redis | TTL 1min |

---

## 六、外部依赖

| 外部服务 | 用途 | 备注 |
|---------|------|------|
| OpenAI / Anthropic | LLM 推理 | 经 ModelGateway 路由 |
| LangSmith | 全链路追踪 | 每轮 Agent 调用记录 span |
| Prometheus | 指标采集 | backend:9090/metrics |
| S3/CDN | 文件存储 | 计划中 |
