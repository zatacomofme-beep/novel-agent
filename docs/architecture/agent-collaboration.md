# Agent Collaboration Pipeline

This project does not run a single "write chapter" prompt.
It runs a staged agent pipeline with validation, revision, and approval loops.

Primary orchestration sources:
- `backend/services/generation_service.py`
- `backend/agents/coordinator.py`
- `backend/tasks/chapter_generation.py`

## 1. End-to-End Sequence

```text
User -> POST /chapters/{chapter_id}/generate
  -> enqueue TaskState + TaskRun + TaskEvent
  -> dispatch to Celery or local async fallback
  -> run_generation_pipeline()

run_generation_pipeline()
  -> load chapter
  -> load Story Bible branch context
  -> validate_story_bible_integrity()
  -> build generation payload
  -> CoordinatorAgent.run()
     -> LibrarianAgent
     -> ArchitectAgent
     -> WriterAgent
     -> revision loop:
        -> CanonGuardianAgent
        -> build_truth_layer_context()
        -> CriticAgent
        -> DebateAgent
        -> EditorAgent
        -> repeat if needed
     -> ApproverAgent
  -> persist chapter update as new version
  -> run evaluate_existing_chapter()
  -> publish task success
```

## 2. Coordinator Is the Real Workflow Engine

`CoordinatorAgent` is the runtime state machine for generation.
It is not just a router.
It owns:

- agent ordering
- revision round limits
- revision stop conditions
- truth-layer propagation between agents
- final approval assembly

Primary source:
- `backend/agents/coordinator.py`

## 3. Per-Agent Responsibilities

| Agent | Main role | Main input | Main output | Why it exists |
| --- | --- | --- | --- | --- |
| `LibrarianAgent` | memory curator | Story Bible context, chapter number/title | `context_brief`, `context_bundle` | turns large canon into a bounded working set |
| `ArchitectAgent` | chapter planner | project metadata, context brief, style guidance | structured `chapter_plan` | separates planning from drafting |
| `WriterAgent` | draft author | chapter plan, context, style guidance | `outline`, `content` | produces first draft under plan constraints |
| `CanonGuardianAgent` | continuity validator | Story Bible + chapter content | `canon_report` | checks chapter against canon facts |
| `CriticAgent` | quality reviewer | content + canon + integrity + truth layer | metrics, issues, `needs_revision` | decides whether revision is necessary |
| `DebateAgent` | revision strategist | review + chapter plan + truth layer | `revision_plan`, `debate_summary` | resolves tension between "protect chapter goal" and "fix problems" |
| `EditorAgent` | revision editor | content + issues + revision plan + truth layer | revised content | applies concrete revision changes |
| `ApproverAgent` | final reviewer | outline + initial/final review + truth layer | `approval` | decides whether chapter is ready to leave generation stage |

Primary sources:
- `backend/agents/librarian.py`
- `backend/agents/architect.py`
- `backend/agents/writer.py`
- `backend/agents/canon_guardian.py`
- `backend/agents/critic.py`
- `backend/agents/debate.py`
- `backend/agents/editor.py`
- `backend/agents/approver.py`

## 4. The Real Center of the Loop: Truth Layer

The smartest part of the pipeline is not the writer.
It is the shared context that lets revision reason about two different failure classes:

- Story Bible integrity issues
- chapter-vs-canon issues

`build_truth_layer_context()` merges both into one revision frame and splits the result into:

- `chapter_revision_targets`
- `story_bible_followups`

That split is crucial.
It prevents the editor from trying to "fix in prose" what is actually a broken source-of-truth problem.

Primary source:
- `backend/services/truth_layer_service.py`

## 5. Revision Loop Logic

The coordinator revision loop works like this:

1. Validate current content against canon.
2. Build truth-layer context from integrity report + canon report.
3. Run critic on the content with that truth-layer context.
4. Stop immediately if revision is no longer needed.
5. Otherwise build a revision plan by debate.
6. Let editor revise the content.
7. Re-run the loop until:
   - quality is acceptable
   - AI taste threshold is acceptable
   - blocking truth-layer issues are gone
   - or max revision rounds are reached

Primary source:
- `backend/agents/coordinator.py`

## 6. Debate Is Not Cosmetic

`DebateAgent` is not a summary generator.
It translates raw issues into a prioritized revision strategy.

It does two important things:

- converts review issues into explicit `action`, `acceptance_criteria`, and severity ordering
- blends ordinary quality issues with truth-layer chapter targets

That means the editor does not revise against a flat list of complaints.
It revises against a ranked plan.

Primary source:
- `backend/agents/debate.py`

## 7. Model Calls Are Optional, Not Assumed

Every agent that uses a model goes through `ModelGateway`.
If OpenAI or Anthropic is unavailable, the pipeline still runs with local fallback logic.

This makes the system more resilient than a pure prompt chain:

- remote generation is preferred
- retry logic exists
- provider selection is centralized
- local fallback still returns usable structured output

Primary source:
- `backend/agents/model_gateway.py`

## 8. Agent Messaging vs Agent Control

There is an in-memory message bus and each agent publishes start/success/error events.
But the real control flow is direct Python orchestration inside `CoordinatorAgent`.

So the message bus is mainly for:

- traceability
- event recording
- observability

It is not the primary execution engine.

Primary sources:
- `backend/agents/base.py`
- `backend/bus/message_bus.py`
- `backend/bus/protocol.py`

## 9. Persistence Boundary

The agent system itself does not own the database transaction of the final chapter.
`run_generation_pipeline()` does.

That function is the boundary where agent outputs become durable state:

- chapter content is written back
- a new chapter version is created
- chapter status is updated
- evaluation is re-run

Primary source:
- `backend/services/generation_service.py`

## 10. Runtime Observability

The pipeline is fully wrapped in a task model:

- task is enqueued and persisted
- progress events are persisted
- task states are streamed over WebSocket
- frontend reloads chapter data after success

This means the user is not waiting on a black-box generation call.
They are interacting with an observable workflow.

Primary sources:
- `backend/tasks/chapter_generation.py`
- `backend/realtime/task_events.py`
- `backend/api/ws.py`
- `frontend/components/editor/use-task-websocket.ts`

## 11. The Practical Meaning of the Pipeline

The system is trying to solve three different problems at once:

1. Write a usable chapter draft
2. Keep that draft inside canon
3. Keep the source-of-truth itself trustworthy

That is why the pipeline is multi-agent.
Each role exists to defend a different failure boundary.
