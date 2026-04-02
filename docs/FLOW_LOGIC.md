# Novel Agent — 逻辑流图

> 描述系统中每个核心模块的内部决策逻辑、分支条件、状态机转换。
> 含 StyleFingerprint / SceneRhythm / RevisionLoop / Foreshadowing / Neo4j 各模块。

---

## 一、Generation Pipeline 逻辑流

```
输入: chapter_id, user_id, payload

1. [G1] TokenBudgetCheck
   IF current_chapter_cost > $2 budget:
     RETURN { status: "budget_exceeded", cost: current_cost }
   END

2. [G2] CheckpointResumeLogic
   last_checkpoint = CheckpointService.get_latest(chapter_id)
   IF last_checkpoint EXISTS:
     writer_segments = last_checkpoint.segments
     resume_from_segment = len(writer_segments) + 1
     logger.info(f"Resuming from segment {resume_from_segment}")
   ELSE:
     resume_from_segment = 1
   END

3. [G3] BuildContextPayload
   payload = {
     story_bible:      load_story_bible(project_id),
     context_bundle:   ContextBuilder.build(project_id, token_limit=MAX_TOKENS*0.4),
     social_topology:  SocialTopologyService.build(project_id),        [新增]
     causal_context:   query_neo4j_causal_paths(chapter.project_id),  [新增]
     open_threads:     ForeshadowingService.get_active(project_id),
     style_fingerprint: UserPreferenceService.get_fingerprint(user_id), [新增]
     ...原有字段
   }

4. [G4] CoordinatorAgent.run(context, payload)
   运行完整 Agent 协作流程（见第二节）

5. [G5] PostProcessing
   L2EpisodicMemory.save_episode(...)
   Neo4jService.create_event_node(chapter_id, ...)
   SemanticCompressionService.compress_if_needed()
   ForeshadowingLifecycleService.scan_and_plant()
   RETURN response
```

---

## 二、Coordinator Agent 逻辑流

```
run(context, payload):
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段 A：准备（PREPARE）                                       │
└─────────────────────────────────────────────────────────────┘
        │
        ├─ A1: LibrarianAgent ──→ context_brief
        │     librarian.run(context, payload)
        │     作用：从 vector_store + L2Episodic 拉取 token 约束内的上下文
        │
        ├─ A2: ArchitectAgent ──→ chapter_plan
        │     architect.run(context, payload)
        │     作用：结合 story_bible + 大纲，生成章节计划（4段结构）
        │
        └─ A3: BuildContextBrief
              构建 context_brief = {
                story_bible, outline_summary,
                character_list, active_threads,
                style_fingerprint.voice_description,  [新增]
                ...原有字段
              }

        ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段 B：生成（GENERATE）                                      │
└─────────────────────────────────────────────────────────────┘
        │
        ├─ B1: WriterAgent
        │     writer.run(context_brief, {
        │       segments_to_generate: [resume_from_segment..4],
        │       voice_description: payload.style_fingerprint.voice_description,
        │       causal_context: payload.causal_context,
        │       social_topology: payload.social_topology,
        │       ...
        │     })
        │     ──→ raw_content
        │     每完成一段: CheckpointService.save(segment_idx, content)
        │
        ├─ B2: CheckpointPersist
        │     保存进度: {segments: [...], content: raw_content, step: "written"}
        │
        └─ B3: BetaReaderAgent
              beta_reader.run(context, {
                content: raw_content,
                tension_data: payload.tension_data,
                persona_archetype: payload.persona_archetype,
                chapter_number: chapter.chapter_number,
                social_topology: payload.social_topology,
                style_fingerprint: payload.style_fingerprint,  [新增]
              })
              ──→ beta_feedback
              (新增 voice_alignment 检查)

        ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段 C：校验（VALIDATE）  ← 提前退出检查                        │
└─────────────────────────────────────────────────────────────┘
        │
        └─ C1: CanonGuardianAgent (pre-check)
              canon_guardian.run(context, { content: raw_content, ... })
              ──→ canon_report
              │
              IF canon_report.blocking_issues > 0:
                RETURN {
                  status: "canon_blocked",
                  blocking_issues: canon_report.blocking_issues,
                  content: raw_content
                }
              END

        ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段 D：Revision Loop（D — Z）                                │
└─────────────────────────────────────────────────────────────┘
        │
        │ loop for round in 1..max_rounds (默认3轮):
        │
        ├─ D1: CanonGuardian ──→ canon_report
        │     { consistency_issues: [...], blocking_issues: int }
        │
        ├─ D2: Critic ──→ review
        │     review = {
        │       issues: [ { dimension, severity, location, description } ],
        │       chaos_interventions: [...],
        │       overall_score: float
        │     }
        │
        ├─ D3: TruthLayerReport
        │     truth_report = build_truth_layer_context(canon_report, review)
        │     payload.truth_layer_context = truth_report
        │
        ├─ D4: Debate ──→ revision_plan
        │     debate.run(context, { content, canon_report, review, truth_report })
        │     revision_plan = {
        │       actions: [ { type, location, instruction, priority } ],
        │       debate_summary: str
        │     }
        │
        ├─ D5: Editor
        │     editor.run(context, {
        │       content,
        │       issues: review.issues,
        │       revision_plan,
        │       beta_feedback,  [新增：注入 BetaReader 反馈]
        │       truth_layer_context,
        │       ...原有参数
        │     })
        │     ──→ revised_content
        │
        ├─ D6: ContentHashCheck
        │     current_hash = hash(revised_content)
        │     IF current_hash == previous_hash:
        │       loop_count += 1
        │       IF loop_count >= 3:
        │         BREAK  # 连续3轮无变化，提前退出
        │       END
        │     ELSE:
        │       loop_count = 0
        │     END
        │
        ├─ D7: TokenBudgetCheck
        │     IF accumulated_cost > $2:
        │       BREAK  # 预算耗尽，提前退出
        │     END
        │
        └─ D8: ExitConditionCheck
              IF round >= max_rounds: BREAK
              IF review.overall_score >= approval_threshold: BREAK
              IF canon_report.blocking_issues == 0 AND review.overall_score > 0.8: BREAK
              ──否则继续下一轮

        ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段 E：审批（APPROVE）                                       │
└─────────────────────────────────────────────────────────────┘
        │
        └─ E1: ApproverAgent
              approver.run(context, {
                content: final_content,
                truth_layer_context,
                beta_feedback,
                ...
              })
              ──→ approval = { approved: bool, reason: str }

        ▼
        RETURN {
          status: "completed",
          content: final_content,
          outline: chapter_plan,
          beta_feedback,
          revision_plans: all_revision_plans,
          canon_report,
          truth_layer_context,
          approval
        }
```

---

## 三、StyleFingerprint Service 逻辑流（新增）

```
build(samples: list[str], user_id: UUID) → StyleFingerprint

1. [SF1] InputValidation
   IF len(samples) < 1:
     RAISE ValueError("至少需要1章写作样章")
   total_words = sum(len(s) for s in samples)
   IF total_words < 5000:
     logger.warning(f"样章总字数{total_words}较少，建议5章以上以提高准确性")
   END

2. [SF2] SentenceStructureAnalysis
   all_sentences = [s for sample in samples for s in split_sentences(sample)]
   sentence_lengths = [len(s.split()) for s in all_sentences]
   sentence_rhythm = {
     avg_len:    mean(sentence_lengths),
     variance:   variance(sentence_lengths),
     median_len: median(sentence_lengths),
     type_dist: {
       declarative: count(s.type == "statement") / len(all_sentences),
       interrogative: count(s.type == "question") / len(all_sentences),
       exclamatory: count(s.type == "exclamation") / len(all_sentences),
     }
   }

3. [SF3] POVMarkersAnalysis
   indirect_discourse = count_free_indirect_discourse(samples)
   inner_monologue_density = count_inner_monologue(samples) / total_words * 1000
   pov_signature = {
     indirect_discourse_ratio: indirect_discourse / len(all_sentences),
     inner_monologue_density: inner_monologue_density,
   }

4. [SF4] LanguageDensityAnalysis
   language_density = {
     adj_per_1000:   count_adjectives(samples) / total_words * 1000,
     adv_per_1000:   count_adverbs(samples) / total_words * 1000,
     verb_strength:  measure_verb_strength(samples),  # 动词的具象程度
   }

5. [SF5] DialoguePatternAnalysis
   dialogue_ratio = count_dialogue_words(samples) / total_words
   speech_verbs = extract_speech_verbs(samples)
   speech_verb_variety = len(set(speech_verbs)) / max(len(speech_verbs), 1)
   dialogue_style = {
     dialogue_ratio:    dialogue_ratio,
     tag_frequency:     "low" if dialogue_ratio < 0.1 else "high",
     speech_verb_variety: speech_verb_variety,
   }

6. [SF6] VoiceDescriptionGeneration
   # LLM 辅助生成，用规则 + LLM 结合
   prompt = f"""
   Based on these writing characteristics:
   - Avg sentence length: {sentence_rhythm.avg_len}
   - Dialogue ratio: {dialogue_style.dialogue_ratio}
   - Adjective density: {language_density.adj_per_1000}
   - Indirect discourse: {pov_signature.indirect_discourse_ratio}

   Generate a 2-3 sentence description of this author's writing voice.
   Format: "Voice: [description]"
   """
   voice_description = LLM.generate(prompt)
   # 例: "克制、听觉优先、碎片化、动作驱动"
   voice_description = clean_voice_description(voice_description)

7. [SF7] Persistence
   fingerprint = StyleFingerprint(
     user_id=user_id,
     sentence_rhythm=sentence_rhythm,
     pov_signature=pov_signature,
     language_density=language_density,
     dialogue_style=dialogue_style,
     voice_description=voice_description,
     sample_chapters=[s[:500] for s in samples],  # 存前500字作为样本
     word_count=total_words,
   )
   db.save(fingerprint)
   RETURN fingerprint

8. [SF8] VoiceConsistencyCheck（BetaReader 调用）
   check(content: str, fingerprint: StyleFingerprint) → VoiceCheckResult:
   current = extract_voice_features(content)
   deviations = []
   IF abs(current.avg_sentence_len - fingerprint.sentence_rhythm.avg_len) > 3:
     deviations.append("avg_sentence_length_mismatch")
   IF abs(current.dialogue_ratio - fingerprint.dialogue_style.dialogue_ratio) > 0.15:
     deviations.append("dialogue_ratio_drift")
   IF abs(current.indirect_discourse_ratio - fingerprint.pov_signature.indirect_discourse_ratio) > 0.1:
     deviations.append("narrative_voice_drift")
   RETURN VoiceCheckResult(
     is_aligned: len(deviations) == 0,
     deviations: deviations,
     alignment_scores: {...}
   )
```

---

## 四、SceneRhythm Service 逻辑流（新增）

```
analyze(content: str, project_id: UUID, chapter_number: int) → RhythmAnalysisResult

1. [SR1] SceneSegmentation
   scenes = segment_by_structure(content)
   # 切分策略：优先按段落标记（空行）、次选固定500-1000字
   IF scene.word_count < 200:
     合并到前一个 scene
   END
   RETURN scenes: list[{scene_idx, text, word_count, start_pos, end_pos}]

2. [SR2] TensionCurveComputation（并行）
   FOR each scene IN scenes:
     tension = TensionSensorService.analyze(scene.text)
     tension_curve.append(tension.score)
   END

3. [SR3] RhythmShapeClassification
   curve = tension_curve
   IF len(curve) < 3:
     shape = "insufficient_data"
   ELSE:
     peaks = count_peaks(curve)
     valleys = count_valleys(curve)
     trend = compute_trend(curve)
     # 形状分类
     IF peaks <= 1 AND valleys <= 1 AND trend.is_flat:
       shape = "flat"
     ELIF peaks == 1 AND valleys == 0 AND trend == "rising":
       shape = "mountain"
     ELIF peaks == 0 AND valleys == 1 AND trend == "falling":
       shape = "valley"
     ELIF peaks >= 2 OR valleys >= 2:
       shape = "dynamic"
     ELSE:
       shape = "atypical"
     END
   END

4. [SR4] BaselineComparison
   baseline = SceneRhythmBaseline.get_or_create(project_id)
   # 更新基线：新章节完成后，将 tension_curve 纳入基线计算
   deviations = []
   FOR i, scene_tension IN enumerate(tension_curve):
     expected = baseline.expected_tension_at_position(i, chapter_number)
     IF abs(scene_tension - expected) > baseline.tolerance_threshold:
       IF scene_tension > expected * 1.3:
         type = "too_intense"
         suggestion = "降低张力，建议增加舒缓场景"
       ELIF scene_tension < expected * 0.7:
         type = "too_flat"
         suggestion = "提升张力，建议增加冲突或悬念"
       deviations.append({scene_idx: i, type, deviation: scene_tension - expected, suggestion})
   END

5. [SR5] RhythmDeviationReport
   RETURN RhythmAnalysisResult(
     scenes=scenes,
     tension_curve=tension_curve,
     shape=shape,
     baseline=baseline,
     deviations=deviations,
     rhythm_score=1 - mean([abs(d.deviation) for d in deviations]) if deviations else 1.0,
   )

6. [SR6] UpdateBaseline（章节完成后调用）
   SceneRhythmBaseline.update(project_id, chapter_number, tension_curve)
   # 滚动窗口：只用最近10章计算基线
```

---

## 五、Foreshadowing Lifecycle 状态机（已有，附逻辑流）

```
状态: OPEN → TRACKING → RESOLUTION_PENDING → RESOLVED / ABANDONED

 lifecycle_transition(thread_id):
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [FL1] OPEN → TRACKING                                    │
│  触发：章节生成时，Architect 检测到伏笔被首次提及           │
│  条件：thread.first_mention_chapter != None              │
│  动作：记录 first_mention_chapter, initial_strength      │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [FL2] TRACKING → RESOLUTION_PENDING                       │
│  触发：Librarian 检测到伏笔接近"该揭晓"的叙事节点           │
│  条件：current_chapter - first_mention >= min_chapters   │
│  动作：标记 resolution_window_start                       │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [FL3] RESOLUTION_PENDING → RESOLVED                       │
│  触发：章节内容中出现伏笔的"揭晓"事件                        │
│  条件：CanonGuardian 检测到 consistency_check PASSED     │
│  动作：记录 resolved_chapter, resolution_quality_score    │
│                                                        │
│  OR → ABANDONED                                         │
│  触发：章节生成完成后，伏笔仍未解决                          │
│  条件：chapter_number >= resolution_window_start + 3    │
│  动作：标记 abandoned_reason = "timeout"                  │
└──────────────────────────────────────────────────────────┘
```

---

## 六、Neo4j 因果图谱逻辑流（新增）

```
因果图谱写入（GenerationService 后处理）:
        │
        ├─→ create_event_node(chapter_event)
        │     创建: (ChapterEvent {chapter_num, summary, tension, ...})
        │     关系: (prev_chapter) -[CAUSED]-> (current_chapter)
        │           (character) -[PARTICIPATED_IN]-> (chapter_event)
        │
        └─→ create_causal_link(prev_event, current_event, cause_type)
              创建: (prev_event) -[CAUSAL_LINK {type, strength}]-> (current_event)

因果图谱查询（GenerationService 准备阶段）:
        │
        ├─→ query_causal_paths(project_id, from_chapter, to_chapter, max_hops)
        │     MATCH path = (a:ChapterEvent)-[r*1..max_hops]->(b:ChapterEvent)
        │     WHERE a.chapter_num = from_chapter AND b.chapter_num = to_chapter
        │     RETURN path
        │     ──→ 供 Architect 了解"因"
        │
        └─→ compute_character_influence(project_id)
              MATCH (c:Character)-[r]-(e:ChapterEvent)
              RETURN c.name, count(r) AS event_count, collect(e.summary)[..3] AS recent_events
              ──→ 供 Writer 了解角色活跃度
```

---

## 七、Token Circuit Breaker 逻辑流

```
on_each_llm_call(task_name, estimated_tokens):
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [CB1] BudgetCheck                                         │
│  IF accumulated_cost + estimated_cost > $2 chapter_budget:│
│    logger.warning(f"Chapter budget exceeded: {accumulated_cost}")
│    RETURN CircuitBreakerOpen(motive="budget_exceeded")    │
│  END                                                      │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [CB2] LoopDetection                                       │
│  current_hash = hash(final_content)                       │
│  IF current_hash == previous_hash:                        │
│    loop_count += 1                                       │
│    IF loop_count >= 3:                                   │
│      logger.warning("Loop detected: 3 rounds no change")
│      RETURN CircuitBreakerOpen(motive="loop_detected")   │
│    END                                                   │
│  ELSE:                                                    │
│    loop_count = 0                                        │
│  END                                                      │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ [CB3] CostAccumulation                                    │
│  accumulated_cost += actual_token_cost                    │
│  prometheus.inc("tokens_used_total", actual_cost)         │
└──────────────────────────────────────────────────────────┘
```
