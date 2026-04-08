import type { KnowledgeTabKey } from "@/components/story-engine/knowledge-base-board";
import type { StoryRoomCloudDraft, Chapter, StoryOutline, StoryChapterSummary, StoryKnowledgeSuggestion, TaskState } from "@/types/api";
import type { StoryRoomLocalDraftSnapshot } from "@/lib/story-room-local-draft";
import type { StoryBibleKnowledgeTab, StoryRoomStageKey } from "./types";
import type { ProcessPlaybackStatus } from "@/components/process-playback-panel";

export function parseListField(value: string): string[] {
  return value
    .split("/")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function readNestedRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function normalizePositiveNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

export function readMetadataNumber(metadata: Record<string, unknown>, key: string): number | null {
  const value = metadata[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function readMetadataString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function readMetadataStringList(metadata: Record<string, unknown>, key: string): string[] {
  const value = metadata[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

export function createClientUuid(): string {
  return crypto.randomUUID();
}

export function extractLatestDraftParagraph(text: string): string | null {
  return (
    text
      .split(/\n\s*\n/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(-1)[0] ?? null
  );
}

export function isStoryBibleKnowledgeTab(tab: KnowledgeTabKey): tab is StoryBibleKnowledgeTab {
  return tab === "locations" || tab === "factions" || tab === "plot_threads";
}

export function buildCloudDraftScopeKey(
  branchId: string | null,
  volumeId: string | null,
  chapterNumber: number,
): string {
  return `${branchId ?? "default"}:${volumeId ?? "default"}:${chapterNumber}`;
}

export function toLocalDraftSnapshotFromCloudDraft(
  draft: StoryRoomCloudDraft,
): StoryRoomLocalDraftSnapshot {
  return {
    projectId: draft.project_id,
    branchId: draft.branch_id,
    volumeId: draft.volume_id,
    chapterNumber: draft.chapter_number,
    chapterTitle: draft.chapter_title,
    draftText: draft.draft_text,
    outlineId: draft.outline_id,
    sourceChapterId: draft.source_chapter_id,
    sourceVersionNumber: draft.source_version_number,
    updatedAt: draft.updated_at,
  };
}

export function normalizeKnowledgeLookupText(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "");
}

export function resolveKnowledgeTabForEntityType(entityType: string): KnowledgeTabKey | null {
  if (
    entityType === "characters" ||
    entityType === "foreshadows" ||
    entityType === "items" ||
    entityType === "locations" ||
    entityType === "factions" ||
    entityType === "plot_threads" ||
    entityType === "world_rules" ||
    entityType === "timeline_events"
  ) {
    return entityType as KnowledgeTabKey;
  }
  return null;
}

export function resolveKnowledgeItemLabel(tab: KnowledgeTabKey, item: Record<string, unknown>): string {
  if (tab === "characters" || tab === "items" || tab === "locations" || tab === "factions") {
    return String(item.name ?? "").trim();
  }
  if (tab === "plot_threads") {
    return String(item.title ?? "").trim();
  }
  if (tab === "world_rules") {
    return String(item.rule_name ?? "").trim();
  }
  if (tab === "timeline_events") {
    return String(item.core_event ?? "").trim();
  }
  return String(item.content ?? "").trim();
}

export function parseStoryRoomStage(value: string | null): "outline" | "draft" | "final" | "knowledge" | "world-building" | null {
  if (
    value === "outline" ||
    value === "draft" ||
    value === "final" ||
    value === "knowledge" ||
    value === "world-building"
  ) {
    return value;
  }
  return null;
}

export function parseStoryRoomChapterNumber(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return Math.trunc(parsed);
}

export function sortChapters(chapters: Chapter[]): Chapter[] {
  return [...chapters].sort((left, right) => {
    const branchCompare = (left.branch_id ?? "").localeCompare(right.branch_id ?? "");
    if (branchCompare !== 0) {
      return branchCompare;
    }
    const volumeCompare = (left.volume_id ?? "").localeCompare(right.volume_id ?? "");
    if (volumeCompare !== 0) {
      return volumeCompare;
    }
    return left.chapter_number - right.chapter_number;
  });
}

export function findCreatedStructureItemId<T extends { id: string }>(
  previousItems: T[],
  nextItems: T[],
): string | null {
  const previousIds = new Set(previousItems.map((item) => item.id));
  return nextItems.find((item) => !previousIds.has(item.id))?.id ?? null;
}

export function isChapterInScope(
  chapter: Chapter,
  branchId: string | null,
  volumeId: string | null,
): boolean {
  if (branchId && chapter.branch_id !== branchId) {
    return false;
  }
  if (volumeId && chapter.volume_id !== volumeId) {
    return false;
  }
  return true;
}

export function buildChapterOutlinePayload(outline: StoryOutline | null): Record<string, unknown> | null {
  if (!outline) {
    return null;
  }
  return {
    outline_id: outline.outline_id,
    parent_id: outline.parent_id,
    level: outline.level,
    title: outline.title,
    content: outline.content,
    status: outline.status,
    version: outline.version,
    node_order: outline.node_order,
    locked: outline.locked,
  };
}

export function buildRecentChapterTexts(
  chapters: Chapter[],
  chapterSummaries: StoryChapterSummary[],
  chapterNumber: number,
): string[] {
  const normalizeInlineText = (value: string): string => value.replace(/\s+/g, " ").trim();
  const truncateInlineText = (value: string, maxLength: number): string => {
    const normalized = normalizeInlineText(value);
    if (normalized.length <= maxLength) {
      return normalized;
    }
    return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
  };
  const buildSuggestionLabel = (item: StoryKnowledgeSuggestion): string =>
    String(
      item.applied_entity_label ??
        item.name ??
        item.title ??
        item.content ??
        item.entity_type ??
        "设定变动",
    ).trim();

  const chapterMap = new Map(chapters.map((chapter) => [chapter.chapter_number, chapter]));
  const summaryMap = new Map(chapterSummaries.map((summary) => [summary.chapter_number, summary]));
  const recentChapterNumbers = Array.from(
    new Set([
      ...chapters.map((chapter) => chapter.chapter_number),
      ...chapterSummaries.map((summary) => summary.chapter_number),
    ]),
  )
    .filter((value) => value < chapterNumber)
    .sort((left, right) => right - left)
    .slice(0, 2);

  return recentChapterNumbers
    .map((value) => {
      const summary = summaryMap.get(value);
      if (summary) {
        const progress = summary.core_progress
          .map((item) => normalizeInlineText(item))
          .filter(Boolean)
          .slice(0, 2);
        const appliedKnowledge = summary.kb_update_suggestions
          .filter((item) => item.status === "applied")
          .map((item) => buildSuggestionLabel(item))
          .filter(Boolean)
          .slice(0, 2);
        const segments = [`第${summary.chapter_number}章总结：${summary.content}`];
        if (progress.length > 0) {
          segments.push(`推进：${progress.join("；")}`);
        }
        if (appliedKnowledge.length > 0) {
          segments.push(`已确认设定：${appliedKnowledge.join("；")}`);
        }
        return truncateInlineText(segments.join(" "), 260);
      }

      const chapter = chapterMap.get(value);
      if (!chapter || chapter.content.trim().length === 0) {
        return "";
      }
      return truncateInlineText(`第${chapter.chapter_number}章正文：${chapter.content}`, 260);
    })
    .filter(Boolean);
}

export function buildCurrentChapterCarryoverPreview(
  summary: StoryChapterSummary | null,
): string[] {
  if (!summary) {
    return [];
  }

  const normalizeInlineText = (value: string): string => value.replace(/\s+/g, " ").trim();
  const truncateInlineText = (value: string, maxLength: number): string => {
    const normalized = normalizeInlineText(value);
    if (normalized.length <= maxLength) {
      return normalized;
    }
    return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
  };
  const appliedKnowledge = summary.kb_update_suggestions
    .filter((item) => item.status === "applied")
    .map((item) =>
      String(
        item.applied_entity_label ??
          item.name ??
          item.title ??
          item.content ??
          item.entity_type ??
          "设定变动",
      ).trim(),
    )
    .filter(Boolean)
    .slice(0, 3);

  const preview: string[] = [];
  if (summary.content.trim()) {
    preview.push(truncateInlineText(summary.content, 180));
  }
  if (summary.core_progress.length > 0) {
    preview.push(
      truncateInlineText(`核心推进：${summary.core_progress.slice(0, 2).join("；")}`, 180),
    );
  }
  if (appliedKnowledge.length > 0) {
    preview.push(truncateInlineText(`已确认设定：${appliedKnowledge.join("；")}`, 180));
  }
  return preview.slice(0, 3);
}

export function selectLatestTask(taskData: TaskState[]): TaskState | null {
  return [...taskData].sort((left, right) => {
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  })[0] ?? null;
}

export function readWorkflowStatusFromTaskResult(
  result: Record<string, unknown> | null | undefined,
): string | null {
  const workflowStatus = result?.workflow_status;
  return typeof workflowStatus === "string" && workflowStatus.trim().length > 0
    ? workflowStatus
    : null;
}

export function readWorkflowStatusFromTaskEventPayload(
  payload: Record<string, unknown> | null | undefined,
): string | null {
  const workflowStatus = payload?.workflow_status;
  return typeof workflowStatus === "string" && workflowStatus.trim().length > 0
    ? workflowStatus
    : null;
}

export function normalizeTaskStatus(status: string, workflowStatus?: string | null): ProcessPlaybackStatus {
  if (workflowStatus === "paused") {
    return "paused";
  }
  if (status === "queued" || status === "running" || status === "succeeded" || status === "failed") {
    return status;
  }
  return "queued";
}

export function normalizeWorkflowStatus(status: string): ProcessPlaybackStatus {
  if (status === "completed") {
    return "succeeded";
  }
  if (status === "failed") {
    return "failed";
  }
  if (status === "paused") {
    return "paused";
  }
  return "running";
}

export function resolveWorkflowStage(workflowType: string): StoryRoomStageKey {
  if (workflowType === "final_optimize") {
    return "final";
  }
  if (workflowType === "outline_stress_test") {
    return "outline";
  }
  if (workflowType.startsWith("entity_generation")) {
    return "knowledge";
  }
  if (workflowType === "bulk_import") {
    return "knowledge";
  }
  return "draft";
}

export function formatWorkflowLabel(workflowType: string): string {
  const labels: Record<string, string> = {
    chapter_stream: "正文生成",
    realtime_guard: "正文检查",
    final_optimize: "终稿收口",
    outline_stress_test: "三级大纲整理",
    bulk_import: "设定导入",
  };
  return labels[workflowType] ?? "最近过程";
}
