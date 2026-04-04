# Legacy Generation Audit

This document records the current relationship between the legacy chapter
generation pipeline and the Story Engine mainline.

It is not a product description. It is an implementation audit used to decide
what can be removed, what must be kept, and what still has no Story Engine
equivalent.

## Scope

Legacy generation chain:

- `services/generation_service.py`
- `agents/coordinator.py`
- `tasks/chapter_generation.py`
- `services/legacy_generation_service.py`
- `services/legacy_generation_dispatch_service.py`

Story Engine mainline:

- `api/v1/story_engine.py`
- `services/story_engine_workflow_service.py`
- `services/story_engine_kb_service.py`
- `frontend/app/dashboard/projects/[projectId]/story-room/page.tsx`

## Summary

Current state:

- Product mainline has already moved to `story-room + Story Engine`.
- Legacy generation still exists for compatibility.
- Legacy generation is now isolated behind explicit compatibility service
  boundaries.
- Legacy API entrypoints are deprecated and hidden from schema.
- Several previously legacy-only chapter-stream enrichments have already moved
  into Story Engine mainline.

Practical conclusion:

- Legacy generation should no longer gain new product functionality.
- Remaining work is ability-by-ability replacement and eventual deletion.

## Ability Mapping

| Legacy ability | Legacy implementation | Story Engine status | Notes |
| --- | --- | --- | --- |
| Unified writer-facing workspace | old editor / chapter endpoints | Covered | Mainline is `story-room` |
| Outline-driven chapter drafting | `Coordinator -> Architect -> Writer` | Covered | Mainline is `chapter-stream` |
| Mid-generation guardrail | `CanonGuardian + Critic + Debate loop` | Covered / reshaped | Mainline is `realtime-guard` plus final optimize |
| Final convergence / polishing | `Editor + Approver` | Covered / reshaped | Mainline is `final-optimize` |
| Structured knowledge write-back | story bible follow-up proposals | Covered | Mainline is chapter summary + KB suggestions |
| Project-level model routing | old direct model usage | Covered | Mainline uses Story Engine routing and guardian consensus |
| Task timeline / playback | legacy task events | Covered | Shared task system is still active |
| Story Bible integrity pre-check | `validate_story_bible_integrity()` | Partially covered | Legacy blocks before generation; Story Engine distributes checks across workflows |
| Checkpoint-based resume | `CheckpointService` | Covered / compatibility-backed | Story Engine chapter stream can now resume from legacy generation checkpoints when no explicit draft state is provided |
| Open thread preload | `foreshadowing_lifecycle_service.get_active_threads()` | Covered | Story Engine chapter stream now injects open threads into generation prompt context |
| L2 episodic memory write | `L2EpisodicMemory.save_episode()` | Covered | Story Engine final optimize now syncs an L2 episodic entry after chapter summary persistence |
| Truth layer report assembly | `build_truth_layer_context()` | Partially covered | Story Engine has guardian consensus and workflow-level summaries, but not the same object contract everywhere |
| Neo4j causal context read/write | `Neo4jService` in legacy generation | Covered / reshaped | Story Engine chapter stream now reads causal context and final optimize writes chapter event nodes |
| Social topology injection | `SocialTopologyService` in generation payload | Covered | Story Engine chapter stream now injects social topology into generation prompt context |
| Token circuit breaker cost report | `token_circuit_breaker` | Covered | Story Engine chapter stream now records cost report and can pause on cost guard |

## Important Findings

### 1. Legacy generation still contains unique capabilities

The following are not yet clearly represented in Story Engine chapter workflows:

- full truth-layer object parity with legacy coordinator loop
- complete coordinator-style revision/debate loop semantics

These are the main blockers to fully deleting the legacy generation path.

### 2. Several legacy abilities are already duplicated by Story Engine

The following should be treated as replacement-complete at the product level:

- chapter drafting mainline
- review/final polish mainline
- chapter-level product entrypoints
- chapter operation API surface used by `story-room`
- stream enrichment with social topology / causal context / open threads
- stream cost guard reporting
- checkpoint-backed resume bootstrap for chapter stream
- final optimize side-effect sync for L2 episodic memory and Neo4j event write-back

### 3. Legacy generation is now implementation-isolated

Direct business-code use of:

- `services.generation_service`
- `tasks.chapter_generation`

should be considered architecture regressions unless they happen inside:

- `services/legacy_generation_service.py`
- `services/legacy_generation_dispatch_service.py`
- tests

## Current Removal Strategy

Recommended order:

1. Keep legacy API compatibility, but do not expose it as product surface.
2. Keep legacy implementation behind compatibility service boundaries.
3. Replace unique uncovered capabilities one by one in Story Engine, if they are still needed.
4. Remove old call sites after coverage is proven.
5. Delete legacy implementation modules last.

## Deletion Readiness

### Not safe to delete yet

- `services/generation_service.py`
- `agents/coordinator.py`
- `tasks/chapter_generation.py`

Reason:

- still used through compatibility paths
- still contains uncovered capabilities
- still contains the coordinator-native revision loop semantics not fully mirrored in Story Engine

### Safe to keep hidden

- old chapter generation API entrypoints
- old beta-reader endpoint
- old generate-next-chapter endpoint

Reason:

- compatibility only
- already hidden from schema

## Guardrail

Architecture rule:

New business code must not import legacy generation implementation directly.

Allowed compatibility boundaries:

- `services/legacy_generation_service.py`
- `services/legacy_generation_dispatch_service.py`
- `services/legacy_project_generation_service.py`

All other new usages should target Story Engine mainline instead.
