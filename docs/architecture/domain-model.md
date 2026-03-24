# Domain Model Deep Dive

This project is a long-form novel production system, not just a chapter generator.
Its core design is:

1. `Story Bible` is the source of truth.
2. `Chapter` is a versioned workflow unit.
3. Quality, canon, review, checkpoint, and final release are all first-class domain concepts.

## 1. Entity Map

```text
User
 ├─ owns -> Project
 ├─ collaborates on -> ProjectCollaborator -> Project
 ├─ has one -> UserPreference
 └─ has many -> PreferenceObservation

Project
 ├─ has many -> ProjectVolume
 ├─ has many -> ProjectBranch
 ├─ has many -> Character / WorldSetting / Location / PlotThread / Foreshadowing / TimelineEvent
 ├─ has many -> Chapter
 ├─ has many -> StoryBibleVersion
 └─ has many -> StoryBiblePendingChange

ProjectBranch
 ├─ may inherit from -> ProjectBranch.source_branch
 ├─ has zero or one -> ProjectBranchStoryBible
 ├─ has many -> Chapter
 ├─ has many -> StoryBibleVersion
 └─ has many -> StoryBiblePendingChange

Chapter
 ├─ belongs to -> Project
 ├─ belongs to -> ProjectVolume
 ├─ belongs to -> ProjectBranch
 ├─ has many -> ChapterVersion
 ├─ has many -> Evaluation
 ├─ has many -> ChapterComment
 ├─ has many -> ChapterReviewDecision
 └─ has many -> ChapterCheckpoint

TaskRun / TaskEvent
 └─ optionally reference -> Chapter / Project / User
```

Authoritative model files:
- `backend/models/project.py`
- `backend/models/project_branch.py`
- `backend/models/project_branch_story_bible.py`
- `backend/models/project_volume.py`
- `backend/models/chapter.py`
- `backend/models/chapter_version.py`
- `backend/models/evaluation.py`
- `backend/models/chapter_comment.py`
- `backend/models/chapter_review_decision.py`
- `backend/models/chapter_checkpoint.py`
- `backend/models/task_run.py`
- `backend/models/task_event.py`
- `backend/models/user_preference.py`
- `backend/models/preference_observation.py`
- `backend/models/story_bible_version.py`

## 2. The Most Important Modeling Decision

The project uses a hybrid Story Bible model:

- Project-level Story Bible data is normalized into concrete tables like `characters`, `locations`, `plot_threads`, and `timeline_events`.
- Branch-level Story Bible changes are not copied into parallel relational tables.
- Instead, branch overrides are stored in `ProjectBranchStoryBible.payload` as JSONB deltas and are resolved at runtime.

This is the key architectural move behind branch inheritance:

- Base project canon stays stable and queryable.
- Branches can diverge without duplicating the full Story Bible.
- Runtime context is assembled by `resolve_story_bible_resolution()` and `load_story_bible_context()`.

Primary sources:
- `backend/services/project_service.py`
- `backend/memory/story_bible.py`

## 3. Domain Layers

### Identity and Collaboration

- `User` is both an owner and a collaborator identity.
- Ownership is modeled by `Project.user_id`.
- Non-owner access is modeled by `ProjectCollaborator`.
- Access is role-driven: `owner`, `editor`, `reviewer`, `viewer`.
- Permissions are enforced in the service layer, not only in the UI.

Primary sources:
- `backend/models/user.py`
- `backend/models/project_collaborator.py`
- `backend/services/project_service.py`

### Project Structure

- Every project is guaranteed to have at least one volume and one branch.
- `ensure_project_structure()` auto-creates a default volume and a default branch when needed.
- Chapters are always scoped by both branch and volume at runtime, even if legacy rows are missing those links.

This means "chapter ordering" is not global across the project.
It is local to `project + branch + volume + chapter_number`.

Primary sources:
- `backend/services/project_service.py`
- `backend/models/project_volume.py`
- `backend/models/project_branch.py`
- `backend/models/chapter.py`

### Story Bible as Truth Source

Project-level sections:
- `Character`
- `WorldSetting`
- `Location`
- `PlotThread`
- `Foreshadowing`
- `TimelineEvent`

Branch-level truth mechanics:
- `ProjectBranchStoryBible` stores branch snapshot deltas.
- `StoryBibleVersion` records versioned changes for a branch.
- `StoryBiblePendingChange` stores proposed but not yet accepted Story Bible updates.

This creates three different truth states:

1. Accepted base truth
2. Branch override truth
3. Proposed future truth

Primary sources:
- `backend/models/project_branch_story_bible.py`
- `backend/models/story_bible_version.py`
- `backend/services/project_service.py`
- `backend/services/story_bible_version_service.py`

### Chapter as Workflow Unit

`Chapter` is not just content storage.
It is the unit that carries:

- current text
- current outline
- current workflow state
- current version number
- latest quality snapshot
- gate metadata derived from checkpoints, reviews, evaluation, integrity, and canon

`ChapterVersion` is append-only history.
Review artifacts store `chapter_version_number`, which means feedback is version-aware by design.

Primary sources:
- `backend/models/chapter.py`
- `backend/models/chapter_version.py`
- `backend/models/chapter_comment.py`
- `backend/models/chapter_review_decision.py`
- `backend/models/chapter_checkpoint.py`
- `backend/services/chapter_service.py`
- `backend/services/review_service.py`

### Evaluation and Gatekeeping

The project intentionally separates:

- `Evaluation` history as append-only records
- `Chapter.quality_metrics` as the latest denormalized snapshot used by the gate

That means the system preserves evaluation history while also keeping a fast "current gate state" on the chapter row.

The final gate is derived, not manually curated.
It is computed from:

- checkpoint state
- review state
- evaluation freshness
- Story Bible integrity blockers
- canon blockers

Primary sources:
- `backend/models/evaluation.py`
- `backend/services/evaluation_service.py`
- `backend/services/chapter_gate_service.py`

### Observability and Learning

Two supporting domains are real subsystems, not side features:

- `TaskRun` and `TaskEvent` persist generation lifecycle and progress
- `UserPreference` and `PreferenceObservation` persist explicit settings plus learned style signals

This matters because generation is not stateless.
It is influenced by:

- current Story Bible branch context
- current chapter position
- explicit user preferences
- inferred long-term style observations

Primary sources:
- `backend/models/task_run.py`
- `backend/models/task_event.py`
- `backend/models/user_preference.py`
- `backend/models/preference_observation.py`
- `backend/services/preference_service.py`

## 4. Key Invariants

- One collaborator row per `project_id + user_id`.
- One branch key per `project_id + key`.
- One branch snapshot row per `project_id + branch_id`.
- One chapter number per `project_id + branch_id + volume_id + chapter_number`.
- One chapter version per `chapter_id + version_number`.
- One user preference profile per `user_id`.
- One Story Bible version number per `project_id + branch_id + version_number`.

These constraints explain why the service layer is careful about:

- resolving default branch and volume
- preventing chapter number collisions when moving chapters
- validating Story Bible section identity fields before saving overrides

## 5. Why This Model Works

The codebase is really built around one idea:

`Project` stores the stable world, `Branch` stores controlled divergence, and `Chapter` stores production state against that divergence.

That is why:

- Story Bible changes can invalidate chapter evaluation
- review artifacts are tied to chapter versions
- final release is blocked by truth-layer problems even when text exists

This is a workflow-centered domain model, not a CRUD-centered one.
