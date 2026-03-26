"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FinalPublishPanel } from "@/components/story-engine/final-publish-panel";
import { DraftStudio } from "@/components/story-engine/draft-studio";
import { FinalDiffViewer } from "@/components/story-engine/final-diff-viewer";
import { ChapterReviewPanel } from "@/components/story-engine/chapter-review-panel";
import {
  ProcessPlaybackPanel,
  type ProcessPlaybackItem,
  type ProcessPlaybackStatus,
  type ProcessPlaybackStep,
} from "@/components/process-playback-panel";
import type { DraftEditorHandle } from "@/components/story-engine/draft-editor-handle";
import { StyleControlPanel } from "@/components/story-engine/style-control-panel";
import { StoryScopeSwitcher } from "@/components/story-engine/story-scope-switcher";
import {
  KnowledgeBaseBoard,
  type KnowledgeSuggestionKind,
  type KnowledgeTabKey,
} from "@/components/story-engine/knowledge-base-board";
import { OutlineWorkbench } from "@/components/story-engine/outline-workbench";
import { apiFetchWithAuth, apiStreamWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import {
  analyzeStoryRoomLocalDraftRecovery,
  buildStoryRoomLocalDraftKey,
  listStoryRoomLocalDrafts,
  readStoryRoomLocalDraft,
  removeStoryRoomLocalDraft,
  summarizeStoryRoomLocalDraft,
  type StoryRoomLocalDraftRecoveryState,
  type StoryRoomLocalDraftSnapshot,
  type StoryRoomLocalDraftSummary,
  writeStoryRoomLocalDraft,
} from "@/lib/story-room-local-draft";
import type {
  Chapter,
  ChapterReviewWorkspace,
  ChapterSelectionRewriteResponse,
  ChapterStreamEvent,
  ChapterVersion,
  FinalOptimizeResponse,
  OutlineStressTestResponse,
  ProjectBootstrapState,
  ProjectStructure,
  ProjectEntityGenerationDispatch,
  ProjectNextChapterCandidate,
  RealtimeGuardResponse,
  RollbackResponse,
  StoryBible,
  StoryBiblePendingChange,
  StoryBiblePendingChangeList,
  StoryBibleVersion,
  StoryBibleVersionList,
  StoryBulkImportResponse,
  StoryEngineWorkspace,
  StoryEngineWorkflowEvent,
  StoryGeneratedCandidateAcceptResponse,
  StoryChapterSummary,
  StoryRoomCloudDraft,
  StoryRoomCloudDraftSummary,
  StoryRoomCloudDraftUpsertRequest,
  StoryKnowledgeSuggestion,
  StoryKnowledgeSuggestionResolveResponse,
  StoryKnowledgeMutationResponse,
  StoryImportTemplate,
  StorySearchResult,
  StoryOutline,
  StyleTemplate,
  TaskEvent,
  TaskPlayback,
  TaskState,
  UserPreferenceProfile,
} from "@/types/api";

type ProjectRouteParams = {
  projectId: string;
};

type PausedStreamState = {
  pausedAtParagraph: number;
  nextParagraphIndex: number;
  paragraphTotal: number;
  currentBeat: string | null;
  remainingBeats: string[];
};

type StreamContinueOptions = {
  resumeFromParagraph?: number | null;
  repairInstruction?: string | null;
  rewriteLatestParagraph?: boolean;
};

type StoryRoomStageKey = "outline" | "draft" | "final" | "knowledge";

type DraftStudioRecoverableDraft = StoryRoomLocalDraftSummary & {
  scopeLabel: string;
  isCurrent: boolean;
};

type StoryRoomWorkflowRun = {
  id: string;
  workflowType: string;
  stage: StoryRoomStageKey;
  label: string;
  title: string;
  summary: string;
  status: ProcessPlaybackStatus;
  progress: number | null;
  updatedAt: string;
  chapterNumber: number | null;
  steps: ProcessPlaybackStep[];
};

function parseStoryRoomStage(value: string | null): StoryRoomStageKey | null {
  if (
    value === "outline" ||
    value === "draft" ||
    value === "final" ||
    value === "knowledge"
  ) {
    return value;
  }
  return null;
}

function parseStoryRoomChapterNumber(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return Math.trunc(parsed);
}

const IMPORT_SECTION_LABELS: Record<string, string> = {
  characters: "人物",
  foreshadows: "伏笔",
  items: "物品",
  world_rules: "规则",
  timeline_events: "时间线",
  outlines: "大纲",
  chapter_summaries: "章节总结",
};

const ENTITY_GENERATION_ENDPOINTS: Record<KnowledgeSuggestionKind, string> = {
  characters: "characters",
  items: "items",
  locations: "locations",
  factions: "factions",
  plot_threads: "plot-threads",
};

const ENTITY_GENERATION_SUCCESS_LABELS: Record<KnowledgeSuggestionKind, string> = {
  characters: "几个人物",
  items: "几件物品",
  locations: "几个地点",
  factions: "一个势力",
  plot_threads: "几条剧情线",
};

const DEFAULT_IMPORT_REPLACE_SECTIONS = Object.keys(IMPORT_SECTION_LABELS);

type StoryBibleKnowledgeTab = Extract<
  KnowledgeTabKey,
  "locations" | "factions" | "plot_threads"
>;

function parseListField(value: string): string[] {
  return value
    .split("/")
    .map((item) => item.trim())
    .filter(Boolean);
}

function readNestedRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function normalizePositiveNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function readMetadataNumber(metadata: Record<string, unknown>, key: string): number | null {
  const value = metadata[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readMetadataString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function readMetadataStringList(metadata: Record<string, unknown>, key: string): string[] {
  const value = metadata[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function buildPausedStreamState(event: ChapterStreamEvent): PausedStreamState | null {
  const metadata = event.metadata ?? {};
  const pausedAtParagraph =
    readMetadataNumber(metadata, "paused_at_paragraph") ?? event.paragraph_index ?? null;
  const nextParagraphIndex = readMetadataNumber(metadata, "next_paragraph_index");
  const paragraphTotal =
    readMetadataNumber(metadata, "paragraph_total") ?? event.paragraph_total ?? null;
  if (pausedAtParagraph === null || nextParagraphIndex === null || paragraphTotal === null) {
    return null;
  }
  return {
    pausedAtParagraph,
    nextParagraphIndex,
    paragraphTotal,
    currentBeat: readMetadataString(metadata, "current_beat"),
    remainingBeats: readMetadataStringList(metadata, "remaining_beats"),
  };
}

function extractLatestDraftParagraph(text: string): string | null {
  return (
    text
      .split(/\n\s*\n/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(-1)[0] ?? null
  );
}

function isStoryBibleKnowledgeTab(tab: KnowledgeTabKey): tab is StoryBibleKnowledgeTab {
  return tab === "locations" || tab === "factions" || tab === "plot_threads";
}

function createClientUuid(): string {
  return crypto.randomUUID();
}

function buildCloudDraftScopeKey(
  branchId: string | null,
  volumeId: string | null,
  chapterNumber: number,
): string {
  return `${branchId ?? "default"}:${volumeId ?? "default"}:${chapterNumber}`;
}

function toLocalDraftSnapshotFromCloudDraft(
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

function selectLatestTask(taskData: TaskState[]): TaskState | null {
  return [...taskData].sort((left, right) => {
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  })[0] ?? null;
}

function readWorkflowStatusFromTaskResult(
  result: Record<string, unknown> | null | undefined,
): string | null {
  const workflowStatus = result?.workflow_status;
  return typeof workflowStatus === "string" && workflowStatus.trim().length > 0
    ? workflowStatus
    : null;
}

function readWorkflowStatusFromTaskEventPayload(
  payload: Record<string, unknown> | null | undefined,
): string | null {
  const workflowStatus = payload?.workflow_status;
  return typeof workflowStatus === "string" && workflowStatus.trim().length > 0
    ? workflowStatus
    : null;
}

function normalizeTaskStatus(status: string, workflowStatus?: string | null): ProcessPlaybackStatus {
  if (workflowStatus === "paused") {
    return "paused";
  }
  if (status === "queued" || status === "running" || status === "succeeded" || status === "failed") {
    return status;
  }
  return "queued";
}

function normalizeWorkflowStatus(status: string): ProcessPlaybackStatus {
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

function resolveWorkflowStage(workflowType: string): StoryRoomStageKey {
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

function formatWorkflowLabel(workflowType: string): string {
  const labels: Record<string, string> = {
    chapter_stream: "正文生成",
    realtime_guard: "正文检查",
    final_optimize: "终稿收口",
    outline_stress_test: "三级大纲整理",
    bulk_import: "设定导入",
  };
  return labels[workflowType] ?? "最近过程";
}

function formatTaskPlaybackLabel(taskType: string): string {
  const labels: Record<string, string> = {
    chapter_generation: "正文生成",
    "story_engine.bulk_import": "导入设定",
    "story_engine.outline_stress_test": "测大纲漏洞",
    "story_engine.chapter_stream": "正文生成",
    "story_engine.realtime_guard": "正文检查",
    "story_engine.final_optimize": "终稿收口",
    "entity_generation.characters": "自动补人物",
    "entity_generation.supporting": "自动补配角",
    "entity_generation.items": "自动补物品",
    "entity_generation.locations": "自动补地点",
    "entity_generation.factions": "自动补势力",
    "entity_generation.plot_threads": "自动补剧情线",
  };
  return labels[taskType] ?? taskType.replaceAll(".", " / ");
}

function resolveTaskPlaybackStage(taskType: string): StoryRoomStageKey {
  if (taskType.startsWith("entity_generation.")) {
    return "knowledge";
  }
  if (taskType === "story_engine.bulk_import") {
    return "knowledge";
  }
  if (taskType.includes("outline")) {
    return "outline";
  }
  if (taskType.includes("final")) {
    return "final";
  }
  return "draft";
}

function summarizeWorkflowEventDetails(event: StoryEngineWorkflowEvent): string | null {
  if (event.message && event.message.trim().length > 0) {
    return event.message.trim();
  }
  const details = event.details ?? {};
  if (typeof details.alert_count === "number") {
    return `发现 ${details.alert_count} 处提醒`;
  }
  if (typeof details.repair_option_count === "number") {
    return `给出 ${details.repair_option_count} 个修法`;
  }
  if (typeof details.remaining_beat_count === "number") {
    return `还要推进 ${details.remaining_beat_count} 个节点`;
  }
  if (typeof details.generated_length === "number") {
    return `当前正文约 ${details.generated_length} 字`;
  }
  if (typeof details.candidate_count === "number") {
    return `整理出 ${details.candidate_count} 条结果`;
  }
  if (typeof details.provider === "string" && details.provider.trim().length > 0) {
    return `${details.provider}${typeof details.model === "string" ? ` / ${details.model}` : ""}`;
  }
  return null;
}

function buildWorkflowPlaybackStep(event: StoryEngineWorkflowEvent): ProcessPlaybackStep {
  return {
    id: `${event.workflow_id}:${event.sequence}`,
    label: event.label,
    detail: summarizeWorkflowEventDetails(event),
    status: normalizeWorkflowStatus(event.status),
    createdAt: event.emitted_at,
  };
}

function buildWorkflowRunFromTimeline(timeline: StoryEngineWorkflowEvent[]): StoryRoomWorkflowRun | null {
  if (timeline.length === 0) {
    return null;
  }
  const lastEvent = timeline[timeline.length - 1];
  const chapterLabel =
    lastEvent.chapter_number !== null
      ? `第 ${lastEvent.chapter_number} 章`
      : "当前内容";
  const progress =
    typeof lastEvent.paragraph_index === "number" &&
    typeof lastEvent.paragraph_total === "number" &&
    lastEvent.paragraph_total > 0
      ? Math.round((lastEvent.paragraph_index / lastEvent.paragraph_total) * 100)
      : normalizeWorkflowStatus(lastEvent.status) === "succeeded"
        ? 100
        : null;
  return {
    id: lastEvent.workflow_id,
    workflowType: lastEvent.workflow_type,
    stage: resolveWorkflowStage(lastEvent.workflow_type),
    label: formatWorkflowLabel(lastEvent.workflow_type),
    title: `${chapterLabel} · ${formatWorkflowLabel(lastEvent.workflow_type)}`,
    summary: summarizeWorkflowEventDetails(lastEvent) ?? lastEvent.label,
    status: normalizeWorkflowStatus(lastEvent.status),
    progress,
    updatedAt: lastEvent.emitted_at,
    chapterNumber: lastEvent.chapter_number,
    steps: timeline
      .slice(-4)
      .map((event) => buildWorkflowPlaybackStep(event))
      .reverse(),
  };
}

function formatTaskPlaybackEventLabel(
  taskType: string,
  eventType: string,
  eventMessage: string | null,
  payload: Record<string, unknown> | null,
): string {
  const workflowLabel =
    typeof payload?.workflow_label === "string" && payload.workflow_label.trim().length > 0
      ? payload.workflow_label.trim()
      : null;
  if (workflowLabel) {
    return workflowLabel;
  }
  if (taskType.startsWith("story_engine.") && eventMessage?.trim()) {
    return eventMessage.trim();
  }
  if (taskType.startsWith("entity_generation.")) {
    const labels: Record<string, string> = {
      queued: "已收下这轮补全",
      dispatched: "已经排进处理队列",
      started: "开始整理当前设定",
      context_loaded: "已装载当前设定",
      generation_started: "正在生成候选",
      generation_completed: "候选初稿已完成",
      outputs_ready: "结果已整理好",
      succeeded: "这轮补全已完成",
      failed: "这轮补全没跑通",
    };
    return labels[eventType] ?? eventType;
  }
  const labels: Record<string, string> = {
    queued: "已收下",
    started: "开始处理",
    succeeded: "已经完成",
    failed: "这轮没跑通",
  };
  return labels[eventType] ?? eventType;
}

function summarizeTaskPlaybackEventPayload(payload: Record<string, unknown> | null): string | null {
  if (!payload) {
    return null;
  }
  if (typeof payload.workflow_message === "string" && payload.workflow_message.trim().length > 0) {
    return payload.workflow_message.trim();
  }
  const workflowEvent =
    payload.workflow_event && typeof payload.workflow_event === "object"
      ? (payload.workflow_event as Record<string, unknown>)
      : null;
  const workflowDetails =
    workflowEvent?.details && typeof workflowEvent.details === "object"
      ? (workflowEvent.details as Record<string, unknown>)
      : null;
  if (typeof workflowDetails?.alert_count === "number") {
    return `发现 ${workflowDetails.alert_count} 处提醒`;
  }
  if (typeof workflowDetails?.repair_option_count === "number") {
    return `给出 ${workflowDetails.repair_option_count} 个修法`;
  }
  if (typeof workflowDetails?.remaining_issue_count === "number") {
    return `剩余 ${workflowDetails.remaining_issue_count} 个问题`;
  }
  if (typeof workflowDetails?.generated_length === "number") {
    return `正文约 ${workflowDetails.generated_length} 字`;
  }
  if (typeof payload.requested_count === "number") {
    return `目标 ${payload.requested_count} 条`;
  }
  if (typeof payload.candidate_count === "number") {
    return `整理出 ${payload.candidate_count} 条`;
  }
  if (typeof payload.returned_count === "number") {
    return `整理出 ${payload.returned_count} 条`;
  }
  if (Array.isArray(payload.entity_preview) && payload.entity_preview.length > 0) {
    const preview = payload.entity_preview
      .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      .slice(0, 2);
    return preview.join(" / ") || null;
  }
  if (typeof payload.response_source === "string") {
    return payload.response_source === "local_fallback" ? "已启用备用方案" : "已走主方案";
  }
  return null;
}

function buildTaskPlaybackSteps(task: TaskPlayback): ProcessPlaybackStep[] {
  if (task.recent_events.length === 0) {
    return [
      {
        id: `${task.task_id}:state`,
        label: task.message?.trim() || "最近过程已记录",
        detail: task.error?.trim() || null,
        status: normalizeTaskStatus(task.status, readWorkflowStatusFromTaskResult(task.result)),
        createdAt: task.updated_at,
      },
    ];
  }
  return task.recent_events
    .slice(-4)
    .map((event) => ({
      id: event.id,
      label: formatTaskPlaybackEventLabel(
        task.task_type,
        event.event_type,
        event.message,
        event.payload,
      ),
      detail: summarizeTaskPlaybackEventPayload(event.payload),
      status: normalizeTaskStatus(
        event.status,
        readWorkflowStatusFromTaskEventPayload(event.payload),
      ),
      createdAt: event.created_at,
    }))
    .reverse();
}

function readWorkflowTimelineMetadata(metadata: Record<string, unknown>): StoryEngineWorkflowEvent[] {
  const value = metadata.workflow_timeline;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is StoryEngineWorkflowEvent =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as StoryEngineWorkflowEvent).workflow_id === "string",
  );
}

function buildFactionKey(name: string, currentKey?: string): string {
  if (currentKey && currentKey.trim().length > 0) {
    return currentKey.trim();
  }
  const normalized = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^0-9a-z\u4e00-\u9fff_-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
  return `faction:${normalized || "entry"}`.slice(0, 100);
}

function resolveStoryBibleEntityKey(item: Record<string, unknown>): string {
  const identityFields = ["id", "key", "name", "title", "content"] as const;
  for (const field of identityFields) {
    const value = item[field];
    if (typeof value === "string" && value.trim().length > 0) {
      return `${field}:${value.trim()}`;
    }
  }
  return "";
}

function resolveKnowledgeEntityId(tab: KnowledgeTabKey, item: Record<string, unknown>): string {
  if (isStoryBibleKnowledgeTab(tab)) {
    return resolveStoryBibleEntityKey(item);
  }
  return String(
    item.character_id ??
      item.foreshadow_id ??
      item.item_id ??
      item.rule_id ??
      item.event_id ??
      "",
  );
}

function buildStoryBiblePayload(
  tab: StoryBibleKnowledgeTab,
  formState: Record<string, string>,
  editingId: string | null,
) {
  if (tab === "locations") {
    const locationId =
      formState.internal_id?.trim() ||
      (editingId && editingId.startsWith("id:") ? editingId.slice(3) : "") ||
      createClientUuid();
    return {
      id: locationId,
      name: formState.name ?? "",
      data: {
        type: formState.location_type || null,
        climate: formState.climate || null,
        population: formState.population || null,
        description: formState.description || null,
        features: parseListField(formState.features ?? ""),
        notable_residents: parseListField(formState.notable_residents ?? ""),
        history: formState.history || null,
      },
      version: normalizePositiveNumber(formState.version, 1),
    };
  }
  if (tab === "factions") {
    return {
      key: buildFactionKey(formState.name ?? "", formState.internal_key),
      name: formState.name ?? "",
      type: formState.type || null,
      scale: formState.scale || null,
      description: formState.description || null,
      goals: formState.goals || null,
      leader: formState.leader || null,
      members: parseListField(formState.members ?? ""),
      territory: formState.territory || null,
      resources: parseListField(formState.resources ?? ""),
      ideology: formState.ideology || null,
      version: normalizePositiveNumber(formState.version, 1),
    };
  }
  const plotThreadId =
    formState.internal_id?.trim() ||
    (editingId && editingId.startsWith("id:") ? editingId.slice(3) : "") ||
    createClientUuid();
  return {
    id: plotThreadId,
    title: formState.title ?? "",
    status: formState.status || "planned",
    importance: normalizePositiveNumber(formState.importance, 1),
    data: {
      type: formState.plot_type || null,
      description: formState.description || null,
      main_characters: parseListField(formState.main_characters ?? ""),
      locations: parseListField(formState.locations ?? ""),
      stages: parseListField(formState.stages ?? ""),
      tension_arc: formState.tension_arc || null,
      resolution: formState.resolution || null,
    },
  };
}

function buildKnowledgePayload(
  tab: KnowledgeTabKey,
  formState: Record<string, string>,
  editingId: string | null,
) {
  if (isStoryBibleKnowledgeTab(tab)) {
    return buildStoryBiblePayload(tab, formState, editingId);
  }
  if (tab === "characters") {
    return {
      name: formState.name ?? "",
      personality: formState.personality ?? null,
      status: formState.status || "active",
      arc_stage: formState.arc_stage || "initial",
      micro_habits: [],
      abilities: {},
      relationships: [],
      arc_boundaries: [],
    };
  }
  if (tab === "foreshadows") {
    return {
      content: formState.content ?? "",
      chapter_planted: formState.chapter_planted ? Number(formState.chapter_planted) : null,
      chapter_planned_reveal: formState.chapter_planned_reveal
        ? Number(formState.chapter_planned_reveal)
        : null,
      status: "pending",
      related_characters: [],
      related_items: [],
    };
  }
  if (tab === "items") {
    return {
      name: formState.name ?? "",
      features: formState.features ?? null,
      owner: formState.owner ?? null,
      location: formState.location ?? null,
      special_rules: [],
    };
  }
  if (tab === "world_rules") {
    return {
      rule_name: formState.rule_name ?? "",
      rule_content: formState.rule_content ?? "",
      scope: formState.scope || "global",
      negative_list: parseListField(formState.negative_list ?? ""),
    };
  }
  return {
    chapter_number: formState.chapter_number ? Number(formState.chapter_number) : null,
    core_event: formState.core_event ?? "",
    location: formState.location ?? null,
    weather: formState.weather ?? null,
    in_universe_time: null,
    character_states: [],
  };
}

function applyResolvedSuggestionToFinalResult(
  current: FinalOptimizeResponse | null,
  resolvedSuggestion: StoryKnowledgeSuggestion,
) {
  if (!current) {
    return current;
  }
  return {
    ...current,
    chapter_summary: {
      ...current.chapter_summary,
      kb_update_suggestions: current.chapter_summary.kb_update_suggestions.map((item) => {
        const suggestionId = String((item as Record<string, unknown>).suggestion_id ?? "");
        return suggestionId === resolvedSuggestion.suggestion_id ? resolvedSuggestion : item;
      }),
    },
    kb_update_list: current.kb_update_list.map((item) =>
      item.suggestion_id === resolvedSuggestion.suggestion_id ? resolvedSuggestion : item,
    ),
  };
}

function buildEditForm(tab: KnowledgeTabKey, item: Record<string, unknown>): Record<string, string> {
  if (tab === "locations") {
    const data = readNestedRecord(item.data);
    return {
      name: String(item.name ?? ""),
      location_type: String(data.type ?? ""),
      climate: String(data.climate ?? ""),
      population: String(data.population ?? ""),
      description: String(data.description ?? ""),
      features: Array.isArray(data.features) ? data.features.join(" / ") : "",
      notable_residents: Array.isArray(data.notable_residents)
        ? data.notable_residents.join(" / ")
        : "",
      history: String(data.history ?? ""),
      internal_id: String(item.id ?? ""),
      version: String(item.version ?? 1),
    };
  }
  if (tab === "factions") {
    return {
      name: String(item.name ?? ""),
      type: String(item.type ?? ""),
      scale: String(item.scale ?? ""),
      description: String(item.description ?? ""),
      goals: String(item.goals ?? ""),
      leader: String(item.leader ?? ""),
      members: Array.isArray(item.members) ? item.members.join(" / ") : "",
      territory: String(item.territory ?? ""),
      resources: Array.isArray(item.resources) ? item.resources.join(" / ") : "",
      ideology: String(item.ideology ?? ""),
      internal_key: String(item.key ?? ""),
      version: String(item.version ?? 1),
    };
  }
  if (tab === "plot_threads") {
    const data = readNestedRecord(item.data);
    return {
      title: String(item.title ?? ""),
      status: String(item.status ?? "planned"),
      importance: String(item.importance ?? 1),
      plot_type: String(data.type ?? ""),
      description: String(data.description ?? ""),
      main_characters: Array.isArray(data.main_characters)
        ? data.main_characters.join(" / ")
        : "",
      locations: Array.isArray(data.locations) ? data.locations.join(" / ") : "",
      stages: Array.isArray(data.stages) ? data.stages.join(" / ") : "",
      tension_arc: String(data.tension_arc ?? ""),
      resolution: String(data.resolution ?? ""),
      internal_id: String(item.id ?? ""),
    };
  }
  if (tab === "characters") {
    return {
      name: String(item.name ?? ""),
      personality: String(item.personality ?? ""),
      status: String(item.status ?? "active"),
      arc_stage: String(item.arc_stage ?? "initial"),
    };
  }
  if (tab === "foreshadows") {
    return {
      content: String(item.content ?? ""),
      chapter_planted: item.chapter_planted ? String(item.chapter_planted) : "",
      chapter_planned_reveal: item.chapter_planned_reveal
        ? String(item.chapter_planned_reveal)
        : "",
    };
  }
  if (tab === "items") {
    return {
      name: String(item.name ?? ""),
      features: String(item.features ?? ""),
      owner: String(item.owner ?? ""),
      location: String(item.location ?? ""),
    };
  }
  if (tab === "world_rules") {
    return {
      rule_name: String(item.rule_name ?? ""),
      rule_content: String(item.rule_content ?? ""),
      scope: String(item.scope ?? ""),
      negative_list: Array.isArray(item.negative_list) ? item.negative_list.join(" / ") : "",
    };
  }
  return {
    chapter_number: item.chapter_number ? String(item.chapter_number) : "",
    core_event: String(item.core_event ?? ""),
    location: String(item.location ?? ""),
    weather: String(item.weather ?? ""),
  };
}

function buildImportSummary(result: StoryBulkImportResponse): string {
  const pieces = Object.entries(result.imported_counts)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `${IMPORT_SECTION_LABELS[key] ?? key}${count}条`);
  const warningText = result.warnings.length > 0 ? ` 提醒：${result.warnings.join("；")}` : "";
  return pieces.length > 0
    ? `整套设定已经落库：${pieces.join("，")}。${warningText}`.trim()
    : `设定包已经导入。${warningText}`.trim();
}

function sortChapters(chapters: Chapter[]): Chapter[] {
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

function findCreatedStructureItemId<T extends { id: string }>(
  previousItems: T[],
  nextItems: T[],
): string | null {
  const previousIds = new Set(previousItems.map((item) => item.id));
  return nextItems.find((item) => !previousIds.has(item.id))?.id ?? null;
}

function isChapterInScope(
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

function buildChapterOutlinePayload(outline: StoryOutline | null): Record<string, unknown> | null {
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

function buildRecentChapterTexts(
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

function buildCurrentChapterCarryoverPreview(
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

function normalizeKnowledgeLookupText(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "");
}

function resolveKnowledgeTabForEntityType(entityType: string): KnowledgeTabKey | null {
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
    return entityType;
  }
  return null;
}

function resolveKnowledgeItemLabel(tab: KnowledgeTabKey, item: Record<string, unknown>): string {
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

function resolveNextChapterCandidate(params: {
  bootstrapCandidate: ProjectNextChapterCandidate | null;
  currentChapterId: string | null;
  currentChapterNumber: number;
  branchId: string | null;
  branchTitle: string | null;
  volumeId: string | null;
  volumeTitle: string | null;
  scopeChapters: Chapter[];
  level3Outlines: StoryOutline[];
}): ProjectNextChapterCandidate | null {
  const {
    bootstrapCandidate,
    currentChapterId,
    currentChapterNumber,
    branchId,
    branchTitle,
    volumeId,
    volumeTitle,
    scopeChapters,
    level3Outlines,
  } = params;

  if (
    bootstrapCandidate &&
    (bootstrapCandidate.chapter_id !== currentChapterId ||
      bootstrapCandidate.chapter_number !== currentChapterNumber)
  ) {
    return bootstrapCandidate;
  }

  const sortedScopeChapters = [...scopeChapters].sort(
    (left, right) => left.chapter_number - right.chapter_number,
  );
  const nextSavedChapter =
    sortedScopeChapters.find((chapter) => chapter.chapter_number > currentChapterNumber) ?? null;
  if (nextSavedChapter) {
    return {
      chapter_id: nextSavedChapter.id,
      chapter_number: nextSavedChapter.chapter_number,
      title: nextSavedChapter.title,
      branch_id: nextSavedChapter.branch_id,
      branch_title: branchTitle,
      volume_id: nextSavedChapter.volume_id,
      volume_title: volumeTitle,
      generation_mode: "existing_draft",
      based_on_blueprint: Boolean(nextSavedChapter.outline),
      has_existing_content: nextSavedChapter.content.trim().length > 0,
    };
  }

  const nextOutline =
    level3Outlines.find((outline) => outline.node_order > currentChapterNumber) ?? null;
  if (nextOutline) {
    return {
      chapter_id: null,
      chapter_number: nextOutline.node_order,
      title: nextOutline.title,
      branch_id: branchId,
      branch_title: branchTitle,
      volume_id: volumeId,
      volume_title: volumeTitle,
      generation_mode: "blueprint_seed",
      based_on_blueprint: true,
      has_existing_content: false,
    };
  }

  return {
    chapter_id: null,
    chapter_number: currentChapterNumber + 1,
    title: null,
    branch_id: branchId,
    branch_title: branchTitle,
    volume_id: volumeId,
    volume_title: volumeTitle,
    generation_mode: "dynamic_continuation",
    based_on_blueprint: false,
    has_existing_content: false,
  };
}

export default function StoryRoomPage() {
  const params = useParams<ProjectRouteParams>();
  const searchParams = useSearchParams();
  const projectId = params.projectId;
  const entryMode = searchParams.get("entry");
  const isNewBookEntry = entryMode === "new-book";
  const requestedStage = parseStoryRoomStage(searchParams.get("stage"));
  const requestedChapterNumber = parseStoryRoomChapterNumber(searchParams.get("chapter"));
  const requestedTool = searchParams.get("tool");
  const hydratedChapterKeyRef = useRef<string | null>(null);
  const queryHydratedRef = useRef<string | null>(null);
  const bootstrapHydratedRef = useRef(false);
  const editorRef = useRef<DraftEditorHandle | null>(null);
  const reviewPanelRef = useRef<HTMLElement | null>(null);

  const [workspace, setWorkspace] = useState<StoryEngineWorkspace | null>(null);
  const [bootstrapState, setBootstrapState] = useState<ProjectBootstrapState | null>(null);
  const [storyBible, setStoryBible] = useState<StoryBible | null>(null);
  const [storyBibleVersions, setStoryBibleVersions] = useState<StoryBibleVersion[]>([]);
  const [storyBiblePendingChanges, setStoryBiblePendingChanges] = useState<
    StoryBiblePendingChange[]
  >([]);
  const [loadingStoryBibleGovernance, setLoadingStoryBibleGovernance] = useState(false);
  const [storyBibleGovernanceActionKey, setStoryBibleGovernanceActionKey] = useState<string | null>(
    null,
  );
  const [preferenceProfile, setPreferenceProfile] = useState<UserPreferenceProfile | null>(null);
  const [styleTemplates, setStyleTemplates] = useState<StyleTemplate[]>([]);
  const [loadingStyleControl, setLoadingStyleControl] = useState(false);
  const [styleActionKey, setStyleActionKey] = useState<string | null>(null);
  const [projectStructure, setProjectStructure] = useState<ProjectStructure | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [selectedVolumeId, setSelectedVolumeId] = useState<string | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [idea, setIdea] = useState("");
  const [genre, setGenre] = useState("");
  const [tone, setTone] = useState("");
  const [targetChapterCount, setTargetChapterCount] = useState(120);
  const [targetTotalWords, setTargetTotalWords] = useState(1_000_000);
  const [targetChapterWords, setTargetChapterWords] = useState(3_000);
  const [sourceMaterial, setSourceMaterial] = useState("");
  const [sourceMaterialName, setSourceMaterialName] = useState<string | null>(null);
  const [stressLoading, setStressLoading] = useState(false);
  const [savingStoryGoals, setSavingStoryGoals] = useState(false);
  const [stressResult, setStressResult] = useState<OutlineStressTestResponse | null>(null);
  const [updatingOutlineId, setUpdatingOutlineId] = useState<string | null>(null);

  const [chapterNumber, setChapterNumber] = useState(1);
  const [chapterTitle, setChapterTitle] = useState("");
  const [draftText, setDraftText] = useState("");
  const [styleSample, setStyleSample] = useState("");
  const [guardResult, setGuardResult] = useState<RealtimeGuardResponse | null>(null);
  const [pausedStreamState, setPausedStreamState] = useState<PausedStreamState | null>(null);
  const [activeRepairInstruction, setActiveRepairInstruction] = useState<string | null>(null);
  const [checkingGuard, setCheckingGuard] = useState(false);
  const [streamingChapter, setStreamingChapter] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [finalResult, setFinalResult] = useState<FinalOptimizeResponse | null>(null);
  const [resolvingSuggestionId, setResolvingSuggestionId] = useState<string | null>(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [localDraftSavedAt, setLocalDraftSavedAt] = useState<string | null>(null);
  const [localDraftRecoveredAt, setLocalDraftRecoveredAt] = useState<string | null>(null);
  const [pendingLocalDraftRecoveryState, setPendingLocalDraftRecoveryState] =
    useState<StoryRoomLocalDraftRecoveryState | null>(null);
  const [pendingLocalDraftSnapshot, setPendingLocalDraftSnapshot] =
    useState<StoryRoomLocalDraftSnapshot | null>(null);
  const [recoverableLocalDrafts, setRecoverableLocalDrafts] = useState<
    StoryRoomLocalDraftSummary[]
  >([]);
  const [cloudDrafts, setCloudDrafts] = useState<StoryRoomCloudDraftSummary[]>([]);
  const [cloudDraftSavedAt, setCloudDraftSavedAt] = useState<string | null>(null);
  const [cloudDraftRecoveredAt, setCloudDraftRecoveredAt] = useState<string | null>(null);
  const [pendingCloudDraftRecoveryState, setPendingCloudDraftRecoveryState] =
    useState<StoryRoomLocalDraftRecoveryState | null>(null);
  const [pendingCloudDraftSnapshot, setPendingCloudDraftSnapshot] =
    useState<StoryRoomCloudDraft | null>(null);
  const [cloudSyncing, setCloudSyncing] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"md" | "txt" | null>(null);
  const [finalizingAction, setFinalizingAction] = useState<"save" | "continue" | null>(null);
  const [reviewWorkspace, setReviewWorkspace] = useState<ChapterReviewWorkspace | null>(null);
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([]);
  const [loadingChapterReview, setLoadingChapterReview] = useState(false);
  const [reviewSubmittingActionKey, setReviewSubmittingActionKey] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<KnowledgeTabKey>("characters");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [highlightedKnowledgeId, setHighlightedKnowledgeId] = useState<string | null>(null);
  const [formState, setFormState] = useState<Record<string, string>>({});
  const [savingKnowledge, setSavingKnowledge] = useState(false);
  const [importingKnowledge, setImportingKnowledge] = useState(false);
  const [importTemplates, setImportTemplates] = useState<StoryImportTemplate[]>([]);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("");
  const [importPayloadText, setImportPayloadText] = useState("");
  const [replaceSections, setReplaceSections] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StorySearchResult[]>([]);
  const [entityTaskState, setEntityTaskState] = useState<TaskState | null>(null);
  const [entityTaskEvents, setEntityTaskEvents] = useState<TaskEvent[]>([]);
  const [projectTaskPlayback, setProjectTaskPlayback] = useState<TaskPlayback[]>([]);
  const [workflowRuns, setWorkflowRuns] = useState<StoryRoomWorkflowRun[]>([]);
  const [dispatchingEntityKind, setDispatchingEntityKind] =
    useState<KnowledgeSuggestionKind | null>(null);
  const [acceptingCandidateIndex, setAcceptingCandidateIndex] = useState<number | null>(null);
  const [activeStage, setActiveStage] = useState<StoryRoomStageKey | null>(null);
  const [pendingStageScroll, setPendingStageScroll] = useState<StoryRoomStageKey | null>(null);
  const [pendingReviewPanelFocus, setPendingReviewPanelFocus] = useState(false);
  const [scopeActionKey, setScopeActionKey] = useState<string | null>(null);

  const outlineList = useMemo(
    () =>
      stressResult
        ? [
            ...stressResult.locked_level_1_outlines,
            ...stressResult.editable_level_2_outlines,
            ...stressResult.editable_level_3_outlines,
          ]
        : workspace?.outlines ?? [],
    [stressResult, workspace?.outlines],
  );

  const selectedBranch = useMemo(
    () =>
      projectStructure?.branches.find((item) => item.id === selectedBranchId) ??
      null,
    [projectStructure?.branches, selectedBranchId],
  );

  const selectedVolume = useMemo(
    () =>
      projectStructure?.volumes.find((item) => item.id === selectedVolumeId) ??
      null,
    [projectStructure?.volumes, selectedVolumeId],
  );

  const scopeChapters = useMemo(
    () =>
      chapters.filter((chapter) =>
        isChapterInScope(chapter, selectedBranchId, selectedVolumeId),
      ),
    [chapters, selectedBranchId, selectedVolumeId],
  );

  const activeChapter = useMemo(() => {
    return (
      scopeChapters.find((chapter) => chapter.chapter_number === chapterNumber) ??
      null
    );
  }, [chapterNumber, scopeChapters]);

  const level3OutlineList = useMemo(
    () =>
      outlineList
        .filter((item) => item.level === "level_3")
        .sort((left, right) => left.node_order - right.node_order),
    [outlineList],
  );

  const currentOutline = useMemo(
    () => outlineList.find((item) => item.level === "level_3" && item.node_order === chapterNumber) ?? null,
    [chapterNumber, outlineList],
  );

  const selectedVolumeTitle = selectedVolume?.title ?? "默认卷";
  const selectedBranchTitle = selectedBranch?.title ?? "默认主线";

  const savedChapterCount = useMemo(
    () => scopeChapters.length,
    [scopeChapters],
  );

  const recentChapterTexts = useMemo(() => {
    return buildRecentChapterTexts(
      scopeChapters,
      workspace?.chapter_summaries ?? [],
      chapterNumber,
    );
  }, [chapterNumber, scopeChapters, workspace?.chapter_summaries]);

  const persistedChapterSummary = useMemo(
    () =>
      (workspace?.chapter_summaries ?? []).find((item) => item.chapter_number === chapterNumber) ?? null,
    [chapterNumber, workspace?.chapter_summaries],
  );

  const visibleFinalResult = useMemo(() => {
    if (finalResult) {
      return finalResult;
    }
    if (
      !persistedChapterSummary ||
      (persistedChapterSummary.kb_update_suggestions?.length ?? 0) === 0
    ) {
      return null;
    }
    return {
      final_draft: draftText,
      revision_notes: [],
      chapter_summary: persistedChapterSummary,
      kb_update_list: persistedChapterSummary.kb_update_suggestions,
      agent_reports: [],
      deliberation_rounds: [],
      original_draft: draftText,
      consensus_rounds: 1,
      consensus_reached: false,
      remaining_issue_count: 0,
      ready_for_publish: false,
      quality_summary: null,
      workflow_timeline: [],
    } satisfies FinalOptimizeResponse;
  }, [draftText, finalResult, persistedChapterSummary]);

  const canApplyOptimizedDraft = useMemo(() => {
    if (!finalResult) {
      return false;
    }
    return finalResult.final_draft.trim().length > 0 && finalResult.final_draft !== draftText;
  }, [draftText, finalResult]);
  const currentChapterCarryoverPreview = useMemo(
    () => buildCurrentChapterCarryoverPreview(finalResult?.chapter_summary ?? persistedChapterSummary),
    [finalResult?.chapter_summary, persistedChapterSummary],
  );
  const knowledgeLookupEntries = useMemo(() => {
    const registerEntries = (
      tab: KnowledgeTabKey,
      items: unknown[],
    ): Array<{
      tab: KnowledgeTabKey;
      itemId: string;
      label: string;
      normalizedLabel: string;
    }> =>
      items.flatMap((rawItem) => {
          if (!rawItem || typeof rawItem !== "object") {
            return [];
          }
          const item = rawItem as Record<string, unknown>;
          const label = resolveKnowledgeItemLabel(tab, item);
          const itemId = resolveKnowledgeEntityId(tab, item);
          if (!label || !itemId) {
            return [];
          }
          return [{
            tab,
            itemId,
            label,
            normalizedLabel: normalizeKnowledgeLookupText(label),
          }];
        });

    return [
      ...registerEntries("characters", workspace?.characters ?? []),
      ...registerEntries("foreshadows", workspace?.foreshadows ?? []),
      ...registerEntries("items", workspace?.items ?? []),
      ...registerEntries("locations", storyBible?.locations ?? []),
      ...registerEntries("factions", storyBible?.factions ?? []),
      ...registerEntries("plot_threads", storyBible?.plot_threads ?? []),
      ...registerEntries("world_rules", workspace?.world_rules ?? []),
      ...registerEntries("timeline_events", workspace?.timeline_events ?? []),
    ];
  }, [
    storyBible?.factions,
    storyBible?.locations,
    storyBible?.plot_threads,
    workspace?.characters,
    workspace?.foreshadows,
    workspace?.items,
    workspace?.timeline_events,
    workspace?.world_rules,
  ]);

  const effectiveTargetChapterCount = useMemo(() => {
    const normalizedTotal = normalizePositiveNumber(String(targetTotalWords), 1_000_000);
    const normalizedPerChapter = normalizePositiveNumber(String(targetChapterWords), 3_000);
    return Math.max(targetChapterCount, 10, Math.ceil(normalizedTotal / normalizedPerChapter));
  }, [targetChapterCount, targetChapterWords, targetTotalWords]);

  const knowledgeItemCount = useMemo(
    () =>
      (workspace?.characters.length ?? 0) +
      (workspace?.items.length ?? 0) +
      (workspace?.foreshadows.length ?? 0) +
      (workspace?.world_rules.length ?? 0) +
      (workspace?.timeline_events.length ?? 0) +
      (storyBible?.locations.length ?? 0) +
      (storyBible?.factions.length ?? 0) +
      (storyBible?.plot_threads.length ?? 0),
    [storyBible, workspace],
  );

  const hasOutlineBlueprint = level3OutlineList.length > 0;
  const hasDraftStarted = Boolean(activeChapter) || draftText.trim().length > 0;
  const hasOptimizationResult = visibleFinalResult !== null;
  const recommendedStage: StoryRoomStageKey = !hasOutlineBlueprint
    ? "outline"
    : !hasDraftStarted
      ? "draft"
      : hasOptimizationResult
        ? "final"
        : "draft";

  const activeStageValue = activeStage ?? recommendedStage;
  const isDraftFocusMode = activeStageValue === "draft";
  const finalizingChapter = finalizingAction !== null;
  const stageCards: Array<{
    key: StoryRoomStageKey;
    title: string;
    status: string;
  }> = [
    {
      key: "outline",
      title: "大纲",
      status: hasOutlineBlueprint ? `${level3OutlineList.length} 条章纲` : "待生成",
    },
    {
      key: "draft",
      title: "正文",
      status: draftText.trim().length > 0 ? `第 ${chapterNumber} 章` : "待起稿",
    },
    {
      key: "final",
      title: "终稿",
      status: hasOptimizationResult ? "结果已出" : "待收口",
    },
    {
      key: "knowledge",
      title: "设定",
      status:
        storyBiblePendingChanges.length > 0
          ? `${storyBiblePendingChanges.length} 条待确认`
          : `${knowledgeItemCount} 条`,
    },
  ];
  const recommendedStageCard =
    stageCards.find((item) => item.key === recommendedStage) ?? stageCards[0];
  const primaryStageActionLabelMap: Record<StoryRoomStageKey, string> = {
    outline: "先定三级大纲",
    draft: hasDraftStarted ? "继续写作" : "开始第一章",
    final: "去终稿收口",
    knowledge: "查看设定",
  };
  const recommendedStageSummaryMap: Record<StoryRoomStageKey, string> = {
    outline: hasOutlineBlueprint ? "三级大纲已经在这里，可以继续调整。" : "先把三级大纲定下来，再开始第一章。",
    draft: hasDraftStarted ? "这一章可以继续往下写。" : "章纲已经有了，直接开始第一章。",
    final: hasOptimizationResult ? "终稿结果已经出来了，可以确认保存并进入下一章。" : "正文完成后，就来这里做终稿收口。",
    knowledge:
      storyBiblePendingChanges.length > 0
        ? "这一轮有新的设定建议，确认后会回写到设定里。"
        : "人物、物品、伏笔和规则都在这里。",
  };

  const scopeLabel = `${selectedBranchTitle} · ${selectedVolumeTitle}`;
  const storyBibleBranchId =
    storyBible?.scope.branch_id ?? selectedBranchId ?? projectStructure?.default_branch_id ?? null;
  const currentLocalDraftKey = useMemo(() => {
    if (!projectStructure) {
      return null;
    }
    return buildStoryRoomLocalDraftKey({
      projectId,
      branchId: selectedBranchId,
      volumeId: selectedVolumeId,
      chapterNumber,
    });
  }, [
    chapterNumber,
    projectId,
    projectStructure,
    selectedBranchId,
    selectedVolumeId,
  ]);
  const currentCloudDraftSummary = useMemo(
    () =>
      cloudDrafts.find(
        (item) =>
          item.scope_key ===
          buildCloudDraftScopeKey(selectedBranchId, selectedVolumeId, chapterNumber),
      ) ?? null,
    [chapterNumber, cloudDrafts, selectedBranchId, selectedVolumeId],
  );
  const currentCloudDraftSnapshotId = currentCloudDraftSummary?.draft_snapshot_id ?? null;
  const currentCloudDraftUpdatedAt = currentCloudDraftSummary?.updated_at ?? null;

  const recoverableDraftCards = useMemo<DraftStudioRecoverableDraft[]>(() => {
    return recoverableLocalDrafts.map((draft) => {
      const branchTitle =
        projectStructure?.branches.find((item) => item.id === draft.branchId)?.title ??
        "默认主线";
      const volumeTitle =
        projectStructure?.volumes.find((item) => item.id === draft.volumeId)?.title ??
        "默认卷";
      return {
        ...draft,
        scopeLabel: `${branchTitle} · ${volumeTitle}`,
        isCurrent: draft.storageKey === currentLocalDraftKey,
      };
    });
  }, [currentLocalDraftKey, projectStructure?.branches, projectStructure?.volumes, recoverableLocalDrafts]);

  const nextChapterCandidate = useMemo(() => {
    return resolveNextChapterCandidate({
      bootstrapCandidate: bootstrapState?.next_chapter ?? null,
      currentChapterId: activeChapter?.id ?? null,
      currentChapterNumber: chapterNumber,
      branchId: selectedBranchId,
      branchTitle: selectedBranchTitle,
      volumeId: selectedVolumeId,
      volumeTitle: selectedVolumeTitle,
      scopeChapters,
      level3Outlines: level3OutlineList,
    });
  }, [
    activeChapter?.id,
    bootstrapState?.next_chapter,
    chapterNumber,
    level3OutlineList,
    scopeChapters,
    selectedBranchId,
    selectedBranchTitle,
    selectedVolumeId,
    selectedVolumeTitle,
  ]);

  const openStage = useCallback((stage: StoryRoomStageKey, options?: { scroll?: boolean }) => {
    setActiveStage(stage);
    if (options?.scroll === false) {
      return;
    }
    setPendingStageScroll(stage);
  }, []);

  const openReviewTool = useCallback(() => {
    setActiveStage("draft");
    setPendingStageScroll("draft");
    setPendingReviewPanelFocus(true);
  }, []);

  const upsertWorkflowRun = useCallback((run: StoryRoomWorkflowRun) => {
    setWorkflowRuns((current) => {
      const next = current.filter((item) => item.id !== run.id);
      next.unshift(run);
      next.sort((left, right) => {
        return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
      });
      return next.slice(0, 8);
    });
  }, []);

  const registerWorkflowEvent = useCallback((event: StoryEngineWorkflowEvent) => {
    const chapterLabel =
      event.chapter_number !== null ? `第 ${event.chapter_number} 章` : "当前内容";
    const progress =
      typeof event.paragraph_index === "number" &&
      typeof event.paragraph_total === "number" &&
      event.paragraph_total > 0
        ? Math.round((event.paragraph_index / event.paragraph_total) * 100)
        : normalizeWorkflowStatus(event.status) === "succeeded"
          ? 100
          : null;

    setWorkflowRuns((current) => {
      const existing = current.find((item) => item.id === event.workflow_id);
      const nextSteps = [
        ...(existing?.steps ?? []).filter((item) => item.id !== `${event.workflow_id}:${event.sequence}`),
        buildWorkflowPlaybackStep(event),
      ]
        .sort((left, right) => {
          return new Date(right.createdAt ?? 0).getTime() - new Date(left.createdAt ?? 0).getTime();
        })
        .slice(0, 4);

      const nextRun: StoryRoomWorkflowRun = {
        id: event.workflow_id,
        workflowType: event.workflow_type,
        stage: resolveWorkflowStage(event.workflow_type),
        label: formatWorkflowLabel(event.workflow_type),
        title: `${chapterLabel} · ${formatWorkflowLabel(event.workflow_type)}`,
        summary: summarizeWorkflowEventDetails(event) ?? event.label,
        status: normalizeWorkflowStatus(event.status),
        progress,
        updatedAt: event.emitted_at,
        chapterNumber: event.chapter_number,
        steps: nextSteps,
      };

      const next = current.filter((item) => item.id !== event.workflow_id);
      next.unshift(nextRun);
      next.sort((left, right) => {
        return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
      });
      return next.slice(0, 8);
    });
  }, []);

  const loadRecoverableLocalDrafts = useCallback(async () => {
    const drafts = await listStoryRoomLocalDrafts(projectId);
    setRecoverableLocalDrafts(drafts);
  }, [projectId]);

  const upsertRecoverableLocalDraft = useCallback(
    (storageKey: string, snapshot: StoryRoomLocalDraftSnapshot) => {
      const nextSummary = summarizeStoryRoomLocalDraft(storageKey, snapshot);
      if (
        nextSummary.chapterTitle.trim().length === 0 &&
        nextSummary.charCount === 0
      ) {
        setRecoverableLocalDrafts((current) =>
          current.filter((item) => item.storageKey !== storageKey),
        );
        return;
      }

      setRecoverableLocalDrafts((current) => {
        const next = current.filter((item) => item.storageKey !== storageKey);
        next.unshift(nextSummary);
        next.sort((left, right) => {
          return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
        });
        return next;
      });
    },
    [],
  );

  const removeRecoverableLocalDraft = useCallback((storageKey: string) => {
    setRecoverableLocalDrafts((current) =>
      current.filter((item) => item.storageKey !== storageKey),
    );
  }, []);

  const upsertCloudDraftSummary = useCallback((draft: StoryRoomCloudDraftSummary) => {
    setCloudDrafts((current) => {
      const next = current.filter((item) => item.draft_snapshot_id !== draft.draft_snapshot_id);
      next.unshift(draft);
      next.sort((left, right) => {
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
      });
      return next;
    });
  }, []);

  const removeCloudDraftSummary = useCallback((draftSnapshotId: string) => {
    setCloudDrafts((current) =>
      current.filter((item) => item.draft_snapshot_id !== draftSnapshotId),
    );
  }, []);

  const loadCloudDrafts = useCallback(async () => {
    if (!isOnline) {
      return;
    }
    try {
      const data = await apiFetchWithAuth<StoryRoomCloudDraftSummary[]>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts`,
      );
      setCloudDrafts(data);
    } catch {
      setCloudDrafts([]);
    }
  }, [isOnline, projectId]);

  const loadCurrentCloudDraft = useCallback(async () => {
    if (!isOnline || !currentCloudDraftSnapshotId) {
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
      setCloudDraftSavedAt(currentCloudDraftUpdatedAt);
      return;
    }

    try {
      const data = await apiFetchWithAuth<StoryRoomCloudDraft | null>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts/${currentCloudDraftSnapshotId}`,
      );
      if (!data) {
        setPendingCloudDraftSnapshot(null);
        setPendingCloudDraftRecoveryState(null);
        setCloudDraftSavedAt(null);
        removeCloudDraftSummary(currentCloudDraftSnapshotId);
        return;
      }

      const cloudSnapshot = toLocalDraftSnapshotFromCloudDraft(data);
      const recovery = analyzeStoryRoomLocalDraftRecovery(cloudSnapshot, {
        chapterId: activeChapter?.id ?? null,
        chapterTitle: activeChapter?.title ?? "",
        draftText: activeChapter?.content ?? "",
        currentVersionNumber: activeChapter?.current_version_number ?? null,
      });

      setPendingCloudDraftSnapshot(recovery?.canRestore ? data : null);
      setPendingCloudDraftRecoveryState(recovery?.canRestore ? recovery.state : null);
      setCloudDraftSavedAt(data.updated_at);
      upsertCloudDraftSummary(data);
    } catch {
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
    }
  }, [
    activeChapter?.content,
    activeChapter?.current_version_number,
    activeChapter?.id,
    activeChapter?.title,
    currentCloudDraftSnapshotId,
    currentCloudDraftUpdatedAt,
    isOnline,
    projectId,
    removeCloudDraftSummary,
    upsertCloudDraftSummary,
  ]);

  const clearCurrentCloudDraft = useCallback(async () => {
    const targetDraftSnapshotId =
      currentCloudDraftSnapshotId ?? pendingCloudDraftSnapshot?.draft_snapshot_id ?? null;
    if (!isOnline || !targetDraftSnapshotId) {
      return;
    }
    try {
      await apiFetchWithAuth<void>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts/${targetDraftSnapshotId}`,
        {
          method: "DELETE",
        },
      );
    } catch {
      return;
    }
    removeCloudDraftSummary(targetDraftSnapshotId);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftSavedAt(null);
    setCloudDraftRecoveredAt(null);
  }, [
    currentCloudDraftSnapshotId,
    isOnline,
    pendingCloudDraftSnapshot?.draft_snapshot_id,
    projectId,
    removeCloudDraftSummary,
  ]);

  const confirmLeaveDirtyDraft = useCallback(
    (nextLabel: string): boolean => {
      if (!draftDirty) {
        return true;
      }
      return window.confirm(
        `当前这一章还有未保存改动，切到${nextLabel}会先离开现在的正文。确认继续吗？`,
      );
    },
    [draftDirty],
  );

  const openPlaybackTarget = useCallback(
    (stage: StoryRoomStageKey, targetChapterNumber: number | null = null) => {
      if (
        targetChapterNumber !== null &&
        targetChapterNumber !== chapterNumber &&
        !confirmLeaveDirtyDraft(`第 ${targetChapterNumber} 章`)
      ) {
        return;
      }
      if (targetChapterNumber !== null) {
        setChapterNumber(targetChapterNumber);
      }
      openStage(stage);
    },
    [chapterNumber, confirmLeaveDirtyDraft, openStage],
  );

  const openNextChapterDraft = useCallback(
    (
      candidate: ProjectNextChapterCandidate | null,
      options: {
        afterFinalize?: boolean;
      } = {},
    ) => {
      const { afterFinalize = false } = options;
      if (!candidate) {
        setError("下一章还没准备好，先回正文区继续整理。");
        return;
      }

      const targetLabel = candidate.title?.trim()
        ? `第 ${candidate.chapter_number} 章《${candidate.title.trim()}》`
        : `第 ${candidate.chapter_number} 章`;
      if (!afterFinalize && !confirmLeaveDirtyDraft(targetLabel)) {
        return;
      }

      setSelectedBranchId(candidate.branch_id);
      setSelectedVolumeId(candidate.volume_id);
      setChapterNumber(candidate.chapter_number);
      setChapterTitle(candidate.title ?? "");
      setDraftText("");
      setDraftDirty(false);
      setGuardResult(null);
      setPausedStreamState(null);
      setActiveRepairInstruction(null);
      setFinalResult(null);
      setStreamStatus(null);
      setPendingLocalDraftSnapshot(null);
      setPendingLocalDraftRecoveryState(null);
      setLocalDraftRecoveredAt(null);
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
      setCloudDraftRecoveredAt(null);
      openStage("draft");

      if (candidate.has_existing_content) {
        setSuccess(`${targetLabel} 已经打开，上一章总结和已确认设定也会一起带过去。`);
        return;
      }

      if (candidate.generation_mode === "blueprint_seed") {
        setSuccess(`${targetLabel} 已就位，章纲、上一章总结和已确认设定都会一起带过去。`);
        return;
      }

      setSuccess(`${targetLabel} 已准备好，上一章总结和已确认设定也会继续带到这一章。`);
    },
    [confirmLeaveDirtyDraft, openStage],
  );

  const openDraftFromOutline = useCallback(() => {
    const targetOutline = currentOutline ?? level3OutlineList[0] ?? null;
    if (
      targetOutline &&
      targetOutline.node_order !== chapterNumber &&
      !confirmLeaveDirtyDraft(`第 ${targetOutline.node_order} 章`)
    ) {
      return;
    }
    if (targetOutline) {
      setChapterNumber(targetOutline.node_order);
      setChapterTitle((current) =>
        current.trim().length > 0 ? current : targetOutline.title,
      );
    }
    openStage("draft");
  }, [chapterNumber, confirmLeaveDirtyDraft, currentOutline, level3OutlineList, openStage]);

  const handlePrimaryStageAction = useCallback(() => {
    if (recommendedStage === "draft" && hasOutlineBlueprint && !hasDraftStarted) {
      openDraftFromOutline();
      return;
    }
    openStage(recommendedStage);
  }, [hasDraftStarted, hasOutlineBlueprint, openDraftFromOutline, openStage, recommendedStage]);

  const handleSelectBranchId = useCallback((branchId: string) => {
    if (branchId === selectedBranchId) {
      return;
    }
    const targetBranch =
      projectStructure?.branches.find((item) => item.id === branchId)?.title ?? "新分线";
    if (!confirmLeaveDirtyDraft(targetBranch)) {
      return;
    }
    setSelectedBranchId(branchId);
  }, [confirmLeaveDirtyDraft, projectStructure?.branches, selectedBranchId]);

  const handleSelectVolumeId = useCallback((volumeId: string) => {
    if (volumeId === selectedVolumeId) {
      return;
    }
    const targetVolume =
      projectStructure?.volumes.find((item) => item.id === volumeId)?.title ?? "新卷";
    if (!confirmLeaveDirtyDraft(targetVolume)) {
      return;
    }
    setSelectedVolumeId(volumeId);
  }, [confirmLeaveDirtyDraft, projectStructure?.volumes, selectedVolumeId]);

  async function handleCreateBranch(payload: {
    title: string;
    description: string | null;
    sourceBranchId: string | null;
    copyChapters: boolean;
    isDefault: boolean;
  }) {
    if (scopeActionKey) {
      return false;
    }

    setScopeActionKey("scope:branch:create");
    setError(null);
    setSuccess(null);

    try {
      const previousBranches = projectStructure?.branches ?? [];
      const structure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/branches`,
        {
          method: "POST",
          body: JSON.stringify({
            title: payload.title,
            description: payload.description,
            source_branch_id: payload.sourceBranchId,
            copy_chapters: payload.copyChapters,
            is_default: payload.isDefault,
          }),
        },
      );
      const chapterData = await apiFetchWithAuth<Chapter[]>(`/api/v1/projects/${projectId}/chapters`);
      setProjectStructure(structure);
      setChapters(sortChapters(chapterData));

      const createdBranchId = findCreatedStructureItemId(previousBranches, structure.branches);
      if (createdBranchId && !draftDirty) {
        setSelectedBranchId(createdBranchId);
      }

      setSuccess(
        createdBranchId && !draftDirty
          ? "新分线已经建好，工作台已切过去。"
          : "新分线已经建好。当前正文有未保存改动，所以还停留在原来的分线。",
      );
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setScopeActionKey(null);
    }
  }

  async function handleUpdateBranch(
    branchId: string,
    payload: {
      title: string;
      description: string | null;
      isDefault: boolean;
    },
  ) {
    if (scopeActionKey) {
      return false;
    }

    setScopeActionKey(`scope:branch:update:${branchId}`);
    setError(null);
    setSuccess(null);

    try {
      const structure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/branches/${branchId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: payload.title,
            description: payload.description,
            is_default: payload.isDefault,
          }),
        },
      );
      setProjectStructure(structure);
      setSuccess("这条分线已经更新。");
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setScopeActionKey(null);
    }
  }

  async function handleCreateVolume(payload: {
    volumeNumber: number | null;
    title: string;
    summary: string | null;
  }) {
    if (scopeActionKey) {
      return false;
    }

    setScopeActionKey("scope:volume:create");
    setError(null);
    setSuccess(null);

    try {
      const previousVolumes = projectStructure?.volumes ?? [];
      const structure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/volumes`,
        {
          method: "POST",
          body: JSON.stringify({
            volume_number: payload.volumeNumber,
            title: payload.title,
            summary: payload.summary,
          }),
        },
      );
      setProjectStructure(structure);

      const createdVolumeId = findCreatedStructureItemId(previousVolumes, structure.volumes);
      if (createdVolumeId && !draftDirty) {
        setSelectedVolumeId(createdVolumeId);
      }

      setSuccess(
        createdVolumeId && !draftDirty
          ? "新卷已经建好，工作台已切过去。"
          : "新卷已经建好。当前正文有未保存改动，所以还停留在原来的卷。",
      );
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setScopeActionKey(null);
    }
  }

  async function handleUpdateVolume(
    volumeId: string,
    payload: {
      volumeNumber: number | null;
      title: string;
      summary: string | null;
    },
  ) {
    if (scopeActionKey) {
      return false;
    }

    setScopeActionKey(`scope:volume:update:${volumeId}`);
    setError(null);
    setSuccess(null);

    try {
      const structure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/volumes/${volumeId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            volume_number: payload.volumeNumber,
            title: payload.title,
            summary: payload.summary,
          }),
        },
      );
      setProjectStructure(structure);
      setSuccess("这一卷已经更新。");
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setScopeActionKey(null);
    }
  }

  function handleSelectOutlineId(outlineId: string) {
    const outline = level3OutlineList.find((item) => item.outline_id === outlineId);
    if (!outline) {
      return;
    }
    if (
      outline.node_order !== chapterNumber &&
      !confirmLeaveDirtyDraft(`第 ${outline.node_order} 章`)
    ) {
      return;
    }
    setActiveStage("draft");
    setChapterNumber(outline.node_order);
  }

  function handleChapterNumberChange(value: number) {
    const nextChapterNumber = Math.max(1, Math.trunc(value || 1));
    if (nextChapterNumber === chapterNumber) {
      return;
    }
    if (!confirmLeaveDirtyDraft(`第 ${nextChapterNumber} 章`)) {
      return;
    }
    setChapterNumber(nextChapterNumber);
  }

  function handleJumpToChapter(targetChapterNumber: number) {
    handleChapterNumberChange(targetChapterNumber);
  }

  function handleChapterTitleInput(value: string) {
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftRecoveredAt(null);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftRecoveredAt(null);
    setChapterTitle(value);
    setDraftDirty(true);
  }

  function handleDraftTextInput(value: string) {
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftRecoveredAt(null);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftRecoveredAt(null);
    setDraftText(value);
    setDraftDirty(true);
  }

  function handleRestoreLocalDraft() {
    if (!pendingLocalDraftSnapshot) {
      return;
    }
    setChapterTitle(pendingLocalDraftSnapshot.chapterTitle);
    setDraftText(pendingLocalDraftSnapshot.draftText);
    setDraftDirty(true);
    setLocalDraftRecoveredAt(pendingLocalDraftSnapshot.updatedAt);
    setLocalDraftSavedAt(pendingLocalDraftSnapshot.updatedAt);
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftRecoveredAt(null);
    setSuccess("已恢复本机暂存的正文。");
  }

  async function clearCurrentLocalDraft() {
    if (!currentLocalDraftKey) {
      return;
    }
    await removeStoryRoomLocalDraft(currentLocalDraftKey);
    removeRecoverableLocalDraft(currentLocalDraftKey);
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftSavedAt(null);
    setLocalDraftRecoveredAt(null);
  }

  function handleDismissLocalDraft() {
    void clearCurrentLocalDraft();
  }

  function handleRestoreCloudDraft() {
    if (!pendingCloudDraftSnapshot) {
      return;
    }
    setChapterTitle(pendingCloudDraftSnapshot.chapter_title);
    setDraftText(pendingCloudDraftSnapshot.draft_text);
    setDraftDirty(true);
    setCloudDraftRecoveredAt(pendingCloudDraftSnapshot.updated_at);
    setCloudDraftSavedAt(pendingCloudDraftSnapshot.updated_at);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftRecoveredAt(null);
    setSuccess("已恢复这份续写稿，现在可以直接接着写。");
  }

  function handleDismissCloudDraft() {
    void clearCurrentCloudDraft();
  }

  function handleOpenRecoverableDraft(draft: DraftStudioRecoverableDraft) {
    const targetLabel = draft.chapterTitle.trim()
      ? `第 ${draft.chapterNumber} 章《${draft.chapterTitle.trim()}》`
      : `第 ${draft.chapterNumber} 章`;

    const changingScope =
      draft.branchId !== selectedBranchId ||
      draft.volumeId !== selectedVolumeId ||
      draft.chapterNumber !== chapterNumber;
    if (changingScope && !confirmLeaveDirtyDraft(targetLabel)) {
      return;
    }

    setSelectedBranchId(draft.branchId);
    setSelectedVolumeId(draft.volumeId);
    setChapterNumber(draft.chapterNumber);
    setActiveStage("draft");
    setPendingStageScroll("draft");
    setSuccess(`${targetLabel} 的本机暂存已经就位，下面可以直接恢复。`);
  }

  const refreshChapterChainState = useCallback(async () => {
    const [structureData, chapterData] = await Promise.all([
      apiFetchWithAuth<ProjectStructure>(`/api/v1/projects/${projectId}/structure`),
      apiFetchWithAuth<Chapter[]>(`/api/v1/projects/${projectId}/chapters`),
    ]);
    setProjectStructure(structureData);
    setChapters(sortChapters(chapterData));
    return { structureData, chapterData };
  }, [projectId]);

  const loadStoryBibleGovernanceState = useCallback(async (
    branchId: string | null,
    showSpinner = true,
  ) => {
    if (showSpinner) {
      setLoadingStoryBibleGovernance(true);
    }

    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const [versionData, pendingData] = await Promise.all([
        apiFetchWithAuth<StoryBibleVersionList>(
          `/api/v1/projects/${projectId}/bible/versions${query}`,
        ),
        apiFetchWithAuth<StoryBiblePendingChangeList>(
          `/api/v1/projects/${projectId}/bible/pending-changes${query}`,
        ),
      ]);
      setStoryBibleVersions(versionData.items);
      setStoryBiblePendingChanges(pendingData.items);
      return { versionData, pendingData };
    } catch (requestError) {
      setStoryBibleVersions([]);
      setStoryBiblePendingChanges([]);
      setError(buildUserFriendlyError(requestError));
      return null;
    } finally {
      if (showSpinner) {
        setLoadingStoryBibleGovernance(false);
      }
    }
  }, [projectId]);

  const loadChapterReviewState = useCallback(async (chapterId: string, showSpinner = true) => {
    if (showSpinner) {
      setLoadingChapterReview(true);
    }
    try {
      const [workspaceData, versionData] = await Promise.all([
        apiFetchWithAuth<ChapterReviewWorkspace>(
          `/api/v1/chapters/${chapterId}/review-workspace`,
        ),
        apiFetchWithAuth<ChapterVersion[]>(`/api/v1/chapters/${chapterId}/versions`),
      ]);
      setReviewWorkspace(workspaceData);
      setChapterVersions(
        [...versionData].sort((left, right) => right.version_number - left.version_number),
      );
      return { workspaceData, versionData };
    } catch (requestError) {
      setReviewWorkspace(null);
      setChapterVersions([]);
      setError(buildUserFriendlyError(requestError));
      return null;
    } finally {
      if (showSpinner) {
        setLoadingChapterReview(false);
      }
    }
  }, []);

  const refreshActiveChapterReviewState = useCallback(async (
    chapterId: string,
    options: {
      refreshChapterChain?: boolean;
    } = {},
  ) => {
    const { refreshChapterChain = false } = options;
    const reviewPromise = loadChapterReviewState(chapterId, false);
    if (refreshChapterChain) {
      await Promise.all([reviewPromise, refreshChapterChainState()]);
      return;
    }
    await reviewPromise;
  }, [loadChapterReviewState, refreshChapterChainState]);

  const loadEntityTaskEvents = useCallback(async (
    taskId: string,
    showError = false,
  ) => {
    try {
      const eventData = await apiFetchWithAuth<TaskEvent[]>(
        `/api/v1/tasks/${taskId}/events`,
      );
      setEntityTaskEvents(eventData);
      return eventData;
    } catch (requestError) {
      setEntityTaskEvents([]);
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return [];
    }
  }, []);

  const loadProjectTaskPlayback = useCallback(async (showError = false) => {
    try {
      const playback = await apiFetchWithAuth<TaskPlayback[]>(
        `/api/v1/projects/${projectId}/task-playback?limit=8&event_limit=5`,
      );
      setProjectTaskPlayback(playback);
      return playback;
    } catch (requestError) {
      setProjectTaskPlayback([]);
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return [];
    }
  }, [projectId]);

  const loadProjectEntityTaskState = useCallback(async (showError = false) => {
    try {
      const taskData = await apiFetchWithAuth<TaskState[]>(
        `/api/v1/projects/${projectId}/tasks?task_type_prefix=entity_generation&limit=8`,
      );
      const latestTask = selectLatestTask(taskData);
      setEntityTaskState(latestTask);
      if (!latestTask) {
        setEntityTaskEvents([]);
        await loadProjectTaskPlayback(showError);
        return null;
      }
      await loadEntityTaskEvents(latestTask.task_id, showError);
      await loadProjectTaskPlayback(showError);
      return latestTask;
    } catch (requestError) {
      setEntityTaskState(null);
      setEntityTaskEvents([]);
      setProjectTaskPlayback([]);
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return null;
    }
  }, [loadEntityTaskEvents, loadProjectTaskPlayback, projectId]);

  const playbackItems = useMemo<ProcessPlaybackItem[]>(() => {
    const localRuns = workflowRuns.map((run) => {
      const actionLabel =
        run.stage === "knowledge"
          ? "去设定区"
          : run.stage === "final"
            ? "去终稿区"
            : run.stage === "outline"
              ? "去大纲区"
              : run.chapterNumber !== null
                ? `回第 ${run.chapterNumber} 章`
                : "回正文区";

      return {
        id: `local:${run.id}`,
        label: run.label,
        title: run.title,
        summary: run.summary,
        status: run.status,
        progress: run.progress,
        updatedAt: run.updatedAt,
        badges: [
          "当前页",
          ...(run.chapterNumber !== null ? [`第 ${run.chapterNumber} 章`] : []),
        ],
        steps: run.steps,
        actionLabel,
        onAction: () => openPlaybackTarget(run.stage, run.chapterNumber),
      } satisfies ProcessPlaybackItem;
    });

    const persistedRuns = projectTaskPlayback.map((task) => {
      const stage = resolveTaskPlaybackStage(task.task_type);
      const actionLabel =
        stage === "knowledge"
          ? "去设定区"
          : stage === "final"
            ? "去终稿区"
            : stage === "outline"
              ? "去大纲区"
              : task.chapter_number !== null
                ? `看第 ${task.chapter_number} 章`
                : "去正文区";
      return {
        id: `task:${task.task_id}`,
        label: formatTaskPlaybackLabel(task.task_type),
        title:
          task.chapter_number !== null
            ? `第 ${task.chapter_number} 章 · ${formatTaskPlaybackLabel(task.task_type)}`
            : formatTaskPlaybackLabel(task.task_type),
        summary: task.message?.trim() || task.error?.trim() || "最近过程已记录。",
        status: normalizeTaskStatus(
          task.status,
          readWorkflowStatusFromTaskResult(task.result),
        ),
        progress: task.progress,
        updatedAt: task.updated_at,
        badges: [
          "项目记录",
          ...(task.chapter_number !== null ? [`第 ${task.chapter_number} 章`] : []),
        ],
        steps: buildTaskPlaybackSteps(task),
        actionLabel,
        onAction: () => openPlaybackTarget(stage, task.chapter_number),
      } satisfies ProcessPlaybackItem;
    });

    return [...localRuns, ...persistedRuns]
      .sort((left, right) => {
        return new Date(right.updatedAt ?? 0).getTime() - new Date(left.updatedAt ?? 0).getTime();
      })
      .slice(0, 6);
  }, [openPlaybackTarget, projectTaskPlayback, workflowRuns]);

  const loadStyleControlState = useCallback(async (showSpinner = true) => {
    if (showSpinner) {
      setLoadingStyleControl(true);
    }

    try {
      const [profileData, templateData] = await Promise.all([
        apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences"),
        apiFetchWithAuth<StyleTemplate[]>("/api/v1/profile/style-templates"),
      ]);
      setPreferenceProfile(profileData);
      setStyleTemplates(templateData);
      return { profileData, templateData };
    } catch (requestError) {
      setPreferenceProfile(null);
      setStyleTemplates([]);
      return null;
    } finally {
      if (showSpinner) {
        setLoadingStyleControl(false);
      }
    }
  }, []);

  const loadStoryBibleForBranch = useCallback(async (
    branchId: string | null,
    showError = false,
  ) => {
    if (!branchId) {
      setStoryBible(null);
      return null;
    }
    try {
      const data = await apiFetchWithAuth<StoryBible>(
        `/api/v1/projects/${projectId}/bible?branch_id=${encodeURIComponent(branchId)}`,
      );
      setStoryBible(data);
      return data;
    } catch (requestError) {
      setStoryBible(null);
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return null;
    }
  }, [projectId]);

  const loadWorkspace = useCallback(async (
    showSpinner = true,
    branchId: string | null = null,
  ) => {
    if (showSpinner) {
      setLoading(true);
    }
    setError(null);
    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const [workspaceData, templateData] = await Promise.all([
        apiFetchWithAuth<StoryEngineWorkspace>(
          `/api/v1/projects/${projectId}/story-engine/workspace${query}`,
        ),
        apiFetchWithAuth<StoryImportTemplate[]>(
          `/api/v1/projects/${projectId}/story-engine/import-templates`,
        ),
        refreshChapterChainState(),
      ]);
      setWorkspace(workspaceData);
      setImportTemplates(templateData);
      setGenre((current) => current || workspaceData.project.genre || "");
      setTone((current) => current || workspaceData.project.tone || "");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  }, [projectId, refreshChapterChainState]);

  const loadProjectBootstrap = useCallback(async (
    options: {
      showError?: boolean;
      branchId?: string | null;
    } = {},
  ) => {
    const { showError = false, branchId = null } = options;
    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const data = await apiFetchWithAuth<ProjectBootstrapState>(
        `/api/v1/projects/${projectId}/bootstrap${query}`,
      );
      setBootstrapState(data);
      if (!bootstrapHydratedRef.current) {
        setIdea((current) => current || data.profile.core_story || "");
        setGenre((current) => current || data.profile.genre || "");
        setTone((current) => current || data.profile.tone || "");
        setTargetChapterCount(data.profile.planned_chapter_count ?? 120);
        setTargetTotalWords(data.profile.target_total_words ?? 1_000_000);
        setTargetChapterWords(data.profile.target_chapter_words ?? 3_000);
        bootstrapHydratedRef.current = true;
      }
      return data;
    } catch (requestError) {
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return null;
    }
  }, [projectId]);

  useEffect(() => {
    bootstrapHydratedRef.current = false;
    setActiveStage(null);
    setWorkflowRuns([]);
    setProjectTaskPlayback([]);
    void loadWorkspace();
  }, [loadWorkspace, projectId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setIsOnline(window.navigator.onLine);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    void loadRecoverableLocalDrafts();
  }, [loadRecoverableLocalDrafts]);

  useEffect(() => {
    if (!isOnline) {
      setCloudSyncing(false);
      return;
    }
    void loadCloudDrafts();
  }, [isOnline, loadCloudDrafts]);

  useEffect(() => {
    if (!projectStructure) {
      return;
    }

    setSelectedBranchId((current) => {
      if (current && projectStructure.branches.some((item) => item.id === current)) {
        return current;
      }
      return projectStructure.default_branch_id ?? projectStructure.branches[0]?.id ?? null;
    });
    setSelectedVolumeId((current) => {
      if (current && projectStructure.volumes.some((item) => item.id === current)) {
        return current;
      }
      return projectStructure.default_volume_id ?? projectStructure.volumes[0]?.id ?? null;
    });
  }, [projectStructure]);

  useEffect(() => {
    if (!selectedBranchId) {
      setStoryBible(null);
      return;
    }
    setStressResult(null);
    setGuardResult(null);
    setPausedStreamState(null);
    setFinalResult(null);
    void loadStoryBibleForBranch(selectedBranchId);
    void loadProjectBootstrap({ branchId: selectedBranchId });
    void loadWorkspace(false, selectedBranchId);
  }, [loadProjectBootstrap, loadStoryBibleForBranch, loadWorkspace, selectedBranchId]);

  useEffect(() => {
    if (draftDirty || scopeChapters.length === 0) {
      return;
    }
    const hasCurrentScopeChapter = scopeChapters.some(
      (chapter) => chapter.chapter_number === chapterNumber,
    );
    if (hasCurrentScopeChapter) {
      return;
    }
    const latestScopeChapter = scopeChapters[scopeChapters.length - 1];
    if (latestScopeChapter && latestScopeChapter.chapter_number !== chapterNumber) {
      setChapterNumber(latestScopeChapter.chapter_number);
    }
  }, [chapterNumber, draftDirty, scopeChapters]);

  useEffect(() => {
    setActiveStage((current) => current ?? recommendedStage);
  }, [recommendedStage]);

  useEffect(() => {
    const queryKey = [
      projectId,
      requestedStage ?? "",
      requestedChapterNumber ?? "",
      requestedTool ?? "",
    ].join(":");
    if (queryHydratedRef.current === queryKey) {
      return;
    }

    if (requestedChapterNumber !== null) {
      setChapterNumber(requestedChapterNumber);
    }

    if (requestedStage) {
      setActiveStage(requestedStage);
      setPendingStageScroll(requestedStage);
    } else if (requestedTool === "review") {
      setActiveStage("draft");
      setPendingStageScroll("draft");
    }

    if (requestedTool === "review") {
      setPendingReviewPanelFocus(true);
    }

    queryHydratedRef.current = queryKey;
  }, [projectId, requestedChapterNumber, requestedStage, requestedTool]);

  useEffect(() => {
    if (!isNewBookEntry || hasOutlineBlueprint) {
      return;
    }
    setActiveStage("outline");
    setPendingStageScroll("outline");
  }, [hasOutlineBlueprint, isNewBookEntry]);

  useEffect(() => {
    if (!pendingReviewPanelFocus || activeStageValue !== "draft") {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      reviewPanelRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      setPendingReviewPanelFocus(false);
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [activeStageValue, pendingReviewPanelFocus]);

  useEffect(() => {
    void loadProjectEntityTaskState();
  }, [loadProjectEntityTaskState, projectId]);

  useEffect(() => {
    void loadStyleControlState();
  }, [loadStyleControlState, projectId]);

  useEffect(() => {
    void loadProjectBootstrap();
  }, [loadProjectBootstrap, projectId]);

  useEffect(() => {
    if (!projectStructure) {
      return;
    }

    const chapterKey =
      activeChapter?.id ??
      `new:${selectedBranchId ?? "default"}:${selectedVolumeId ?? "default"}:${chapterNumber}`;
    const switchingChapter = hydratedChapterKeyRef.current !== chapterKey;
    if (!switchingChapter && draftDirty) {
      return;
    }

    setChapterTitle(activeChapter?.title ?? "");
    setDraftText(activeChapter?.content ?? "");
    if (switchingChapter) {
      setGuardResult(null);
      setPausedStreamState(null);
      setActiveRepairInstruction(null);
      setFinalResult(null);
      setStreamStatus(null);
      setLocalDraftRecoveredAt(null);
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
      setCloudDraftRecoveredAt(null);
    }
    hydratedChapterKeyRef.current = chapterKey;
    setDraftDirty(false);

    let cancelled = false;
    const loadLocalDraftSnapshot = async () => {
      const localDraftSnapshot = currentLocalDraftKey
        ? await readStoryRoomLocalDraft(currentLocalDraftKey)
        : null;
      if (cancelled) {
        return;
      }

      const recovery = localDraftSnapshot
        ? analyzeStoryRoomLocalDraftRecovery(localDraftSnapshot, {
            chapterId: activeChapter?.id ?? null,
            chapterTitle: activeChapter?.title ?? "",
            draftText: activeChapter?.content ?? "",
            currentVersionNumber: activeChapter?.current_version_number ?? null,
          })
        : null;

      setPendingLocalDraftSnapshot(
        localDraftSnapshot && recovery?.canRestore ? localDraftSnapshot : null,
      );
      setPendingLocalDraftRecoveryState(
        localDraftSnapshot && recovery?.canRestore ? recovery.state : null,
      );
      setLocalDraftSavedAt(localDraftSnapshot?.updatedAt ?? null);
    };

    void loadLocalDraftSnapshot();
    return () => {
      cancelled = true;
    };
  }, [
    activeChapter?.content,
    activeChapter?.current_version_number,
    activeChapter?.id,
    activeChapter?.title,
    chapterNumber,
    currentLocalDraftKey,
    draftDirty,
    projectStructure,
    selectedBranchId,
    selectedVolumeId,
  ]);

  useEffect(() => {
    if (draftDirty) {
      return;
    }
    void loadCurrentCloudDraft();
  }, [draftDirty, loadCurrentCloudDraft]);

  useEffect(() => {
    if (!draftDirty || !currentLocalDraftKey || !projectStructure) {
      return;
    }

    // 正文输入、流式生成和标题修改都先落一份本机暂存，避免刷新或崩溃直接丢稿。
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        if (!chapterTitle.trim() && !draftText.trim()) {
          await removeStoryRoomLocalDraft(currentLocalDraftKey);
          removeRecoverableLocalDraft(currentLocalDraftKey);
          setLocalDraftSavedAt(null);
          return;
        }

        const snapshot: StoryRoomLocalDraftSnapshot = {
          projectId,
          branchId: selectedBranchId,
          volumeId: selectedVolumeId,
          chapterNumber,
          chapterTitle,
          draftText,
          outlineId: currentOutline?.outline_id ?? null,
          sourceChapterId: activeChapter?.id ?? null,
          sourceVersionNumber: activeChapter?.current_version_number ?? null,
          updatedAt: new Date().toISOString(),
        };
        await writeStoryRoomLocalDraft(currentLocalDraftKey, snapshot);
        upsertRecoverableLocalDraft(currentLocalDraftKey, snapshot);
        setLocalDraftSavedAt(snapshot.updatedAt);
      })();
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [
    activeChapter?.current_version_number,
    activeChapter?.id,
    chapterNumber,
    chapterTitle,
    currentLocalDraftKey,
    currentOutline?.outline_id,
    draftDirty,
    draftText,
    projectId,
    projectStructure,
    removeRecoverableLocalDraft,
    selectedBranchId,
    selectedVolumeId,
    upsertRecoverableLocalDraft,
  ]);

  useEffect(() => {
    if (
      !draftDirty ||
      !isOnline ||
      !projectStructure ||
      savingDraft ||
      finalizingAction !== null ||
      reviewSubmittingActionKey !== null
    ) {
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        if (!chapterTitle.trim() && !draftText.trim()) {
          await clearCurrentCloudDraft();
          return;
        }

        setCloudSyncing(true);
        try {
          const payload: StoryRoomCloudDraftUpsertRequest = {
            branch_id: selectedBranchId,
            volume_id: selectedVolumeId,
            chapter_number: chapterNumber,
            chapter_title: chapterTitle,
            draft_text: draftText,
            outline_id: currentOutline?.outline_id ?? null,
            source_chapter_id: activeChapter?.id ?? null,
            source_version_number: activeChapter?.current_version_number ?? null,
          };
          const draft = await apiFetchWithAuth<StoryRoomCloudDraft>(
            `/api/v1/projects/${projectId}/story-engine/cloud-drafts/current`,
            {
              method: "PUT",
              body: JSON.stringify(payload),
            },
          );
          if (cancelled) {
            return;
          }
          upsertCloudDraftSummary(draft);
          setCloudDraftSavedAt(draft.updated_at);
        } catch {
          // 云端续存失败时保留现有页面状态，避免打断当前写作。
        } finally {
          if (!cancelled) {
            setCloudSyncing(false);
          }
        }
      })();
    }, 1200);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [
    activeChapter?.current_version_number,
    activeChapter?.id,
    chapterNumber,
    chapterTitle,
    clearCurrentCloudDraft,
    currentOutline?.outline_id,
    draftDirty,
    draftText,
    isOnline,
    finalizingAction,
    projectId,
    projectStructure,
    reviewSubmittingActionKey,
    savingDraft,
    selectedBranchId,
    selectedVolumeId,
    upsertCloudDraftSummary,
  ]);

  useEffect(() => {
    if (!draftDirty && !streamingChapter && !savingDraft) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [draftDirty, savingDraft, streamingChapter]);

  useEffect(() => {
    if (!activeChapter?.id) {
      setExportingFormat(null);
      setFinalizingAction(null);
      return;
    }
    setExportingFormat(null);
    setFinalizingAction(null);
  }, [activeChapter?.id]);

  useEffect(() => {
    if (activeChapter || !currentOutline || draftText.trim().length > 0) {
      return;
    }
    setChapterTitle((current) => (current.trim().length > 0 ? current : currentOutline.title));
  }, [activeChapter, currentOutline, draftText]);

  useEffect(() => {
    if (!activeChapter?.id) {
      setReviewWorkspace(null);
      setChapterVersions([]);
      setLoadingChapterReview(false);
      return;
    }
    void loadChapterReviewState(activeChapter.id);
  }, [activeChapter?.current_version_number, activeChapter?.id, loadChapterReviewState]);

  useEffect(() => {
    if (!pendingStageScroll || activeStageValue !== pendingStageScroll) {
      return;
    }

    let frameId = 0;
    let attempts = 0;

    const tryScroll = () => {
      const target = document.getElementById(`story-stage-${pendingStageScroll}`);
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        setPendingStageScroll(null);
        return;
      }

      if (attempts >= 8) {
        setPendingStageScroll(null);
        return;
      }

      attempts += 1;
      frameId = window.requestAnimationFrame(tryScroll);
    };

    frameId = window.requestAnimationFrame(tryScroll);
    return () => window.cancelAnimationFrame(frameId);
  }, [activeStageValue, pendingStageScroll]);

  useEffect(() => {
    void loadStoryBibleGovernanceState(storyBibleBranchId);
  }, [loadStoryBibleGovernanceState, projectId, storyBibleBranchId]);

  useEffect(() => {
    if (!entityTaskState) {
      return;
    }
    if (entityTaskState.status !== "queued" && entityTaskState.status !== "running") {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadProjectEntityTaskState();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [entityTaskState, loadProjectEntityTaskState]);

  async function handleSaveStoryGoals(showSuccessHint = true) {
    setSavingStoryGoals(true);
    setError(null);
    if (showSuccessHint) {
      setSuccess(null);
    }

    try {
      const profile = bootstrapState?.profile;
      const query = selectedBranchId ? `?branch_id=${encodeURIComponent(selectedBranchId)}` : "";
      const data = await apiFetchWithAuth<ProjectBootstrapState>(
        `/api/v1/projects/${projectId}/bootstrap${query}`,
        {
          method: "PUT",
          body: JSON.stringify({
            genre: genre || null,
            theme: profile?.theme ?? null,
            tone: tone || null,
            protagonist_name: profile?.protagonist_name ?? null,
            protagonist_summary: profile?.protagonist_summary ?? null,
            supporting_cast: profile?.supporting_cast ?? [],
            world_background: profile?.world_background ?? null,
            core_story: idea || null,
            novel_style: profile?.novel_style ?? null,
            prose_style: profile?.prose_style ?? null,
            target_total_words: targetTotalWords,
            target_chapter_words: targetChapterWords,
            planned_chapter_count: effectiveTargetChapterCount,
            special_requirements: profile?.special_requirements ?? null,
          }),
        },
      );
      setBootstrapState(data);
      bootstrapHydratedRef.current = true;
      if (showSuccessHint) {
        setSuccess("这本书的题材、气质和体量设定已经保存到项目里了。");
      }
      return data;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return null;
    } finally {
      setSavingStoryGoals(false);
    }
  }

  function handleSourceMaterialChange(value: string, name?: string | null) {
    setSourceMaterial(value);
    if (name !== undefined) {
      setSourceMaterialName(name);
    }
  }

  function handleClearSourceMaterial() {
    setSourceMaterial("");
    setSourceMaterialName(null);
  }

  async function handleUpdateOutline(
    outlineId: string,
    payload: {
      title: string;
      content: string;
    },
  ) {
    setUpdatingOutlineId(outlineId);
    setError(null);
    setSuccess(null);
    try {
      const updated = await apiFetchWithAuth<StoryOutline>(
        `/api/v1/projects/${projectId}/story-engine/outlines/${outlineId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: payload.title,
            content: payload.content,
          }),
        },
      );
      setStressResult((current) => {
        if (!current) {
          return current;
        }
        const replaceOutline = (items: StoryOutline[]) =>
          items.map((item) => (item.outline_id === outlineId ? updated : item));
        return {
          ...current,
          locked_level_1_outlines: replaceOutline(current.locked_level_1_outlines),
          editable_level_2_outlines: replaceOutline(current.editable_level_2_outlines),
          editable_level_3_outlines: replaceOutline(current.editable_level_3_outlines),
        };
      });
      await loadWorkspace(false, selectedBranchId);
      setSuccess("大纲节点已经更新。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setUpdatingOutlineId(null);
    }
  }

  async function handleRunStressTest() {
    if (!(await handleSaveStoryGoals(false))) {
      return;
    }
    setStressLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<OutlineStressTestResponse>(
        `/api/v1/projects/${projectId}/story-engine/workflows/outline-stress-test`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_id: selectedBranchId,
            idea: idea.trim() || null,
            genre: genre || null,
            tone: tone || null,
            target_chapter_count: effectiveTargetChapterCount,
            target_total_words: targetTotalWords,
            source_material: sourceMaterial.trim() || null,
            source_material_name: sourceMaterialName,
          }),
        },
      );
      setStressResult(data);
      const workflowRun = buildWorkflowRunFromTimeline(data.workflow_timeline ?? []);
      if (workflowRun) {
        upsertWorkflowRun(workflowRun);
      }
      setActiveStage("outline");
      setPendingStageScroll("outline");
      setSuccess("三级大纲已经压好了，先确认章纲，再开始第一章。");
      await Promise.all([
        loadWorkspace(false, selectedBranchId),
        loadProjectBootstrap({ branchId: selectedBranchId }),
        loadProjectTaskPlayback(),
      ]);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStressLoading(false);
    }
  }

  const triggerGuardCheck = useCallback(async (showSuccess: boolean) => {
    setCheckingGuard(true);
    try {
      const data = await apiFetchWithAuth<RealtimeGuardResponse>(
        `/api/v1/projects/${projectId}/story-engine/workflows/realtime-guard`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_id: selectedBranchId,
            chapter_id: activeChapter?.id ?? null,
            chapter_number: chapterNumber,
            chapter_title: chapterTitle || null,
            outline_id: currentOutline?.outline_id ?? null,
            current_outline: currentOutline?.content ?? null,
            recent_chapters: recentChapterTexts,
            draft_text: draftText,
            latest_paragraph: extractLatestDraftParagraph(draftText),
          }),
        },
      );
      setGuardResult(data);
      const workflowRun = buildWorkflowRunFromTimeline(data.workflow_timeline ?? []);
      if (workflowRun) {
        upsertWorkflowRun(workflowRun);
      }
      if (showSuccess && data.alerts.length === 0) {
        setSuccess("本章暂时没发现明显的人设和设定硬伤。");
      }
    } catch (requestError) {
      if (showSuccess) {
        setError(buildUserFriendlyError(requestError));
      }
    } finally {
      setCheckingGuard(false);
    }
  }, [
    activeChapter?.id,
    chapterNumber,
    chapterTitle,
    currentOutline?.content,
    currentOutline?.outline_id,
    draftText,
    projectId,
    recentChapterTexts,
    selectedBranchId,
    upsertWorkflowRun,
  ]);

  useEffect(() => {
    if (streamingChapter || draftText.trim().length < 80) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      void triggerGuardCheck(false);
    }, 900);
    return () => window.clearTimeout(timeoutId);
  }, [draftText, chapterNumber, chapterTitle, outlineList, streamingChapter, triggerGuardCheck]);

  async function handleRunStreamGenerate(options: StreamContinueOptions = {}) {
    const resumeFromParagraph = options.resumeFromParagraph ?? null;
    const repairInstruction = options.repairInstruction ?? null;
    const rewriteLatestParagraph = options.rewriteLatestParagraph ?? false;
    const isResume = resumeFromParagraph !== null;

    setStreamingChapter(true);
    setActiveRepairInstruction(repairInstruction);
    setStreamStatus(
      isResume
        ? rewriteLatestParagraph
          ? "正在把刚才那段修平，然后从停下的位置继续往下写..."
          : "正在复查你当前的修改，并从停下的位置继续往下写..."
        : "正在根据细纲顺正文...",
    );
    setError(null);
    setSuccess(null);
    setFinalResult(null);
    if (!isResume) {
      setGuardResult(null);
      setPausedStreamState(null);
    }

    try {
      await apiStreamWithAuth<ChapterStreamEvent>(
        `/api/v1/projects/${projectId}/story-engine/workflows/chapter-stream`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_id: selectedBranchId,
            chapter_id: activeChapter?.id ?? null,
            chapter_number: chapterNumber,
            chapter_title: chapterTitle || null,
            outline_id: currentOutline?.outline_id ?? null,
            current_outline: currentOutline?.content ?? null,
            recent_chapters: recentChapterTexts,
            existing_text: draftText,
            style_sample: styleSample || null,
            target_word_count: 2400,
            target_paragraph_count: 5,
            resume_from_paragraph: resumeFromParagraph,
            repair_instruction: repairInstruction,
            rewrite_latest_paragraph: rewriteLatestParagraph,
          }),
        },
        async (event) => {
          if (event.workflow_event) {
            registerWorkflowEvent(event.workflow_event);
          }
          const workflowTimeline = readWorkflowTimelineMetadata(event.metadata ?? {});
          if (workflowTimeline.length > 0) {
            const workflowRun = buildWorkflowRunFromTimeline(workflowTimeline);
            if (workflowRun) {
              upsertWorkflowRun(workflowRun);
            }
          }

          if (event.event === "start") {
            setStreamStatus(event.message ?? "正在整理本章推进节奏...");
            if (event.text) {
              setDraftText(event.text);
              setDraftDirty(true);
            }
            if (isResume) {
              setGuardResult(null);
              setPausedStreamState(null);
            }
            return;
          }

          if (event.event === "plan") {
            setStreamStatus(event.message ?? "正在整理本章推进节奏...");
            return;
          }

          if (event.event === "chunk") {
            setStreamStatus(
              event.message ??
                `正在写第 ${event.paragraph_index ?? 1}/${event.paragraph_total ?? 1} 段...`,
            );
            if (event.text) {
              setDraftText(event.text);
              setDraftDirty(true);
            } else if (event.delta) {
              setDraftDirty(true);
              setDraftText((current) => `${current}${event.delta ?? ""}`);
            }
            return;
          }

          if (event.event === "guard") {
            if (event.text) {
              setDraftText(event.text);
              setDraftDirty(true);
            }
            if (event.guard_result) {
              setGuardResult(event.guard_result);
            }
            const nextPausedState = buildPausedStreamState(event);
            setPausedStreamState(nextPausedState);
            setStreamStatus(event.message ?? "发现设定冲突，已经暂停起稿。");
            setSuccess(
              nextPausedState
                ? `正文已停在第 ${nextPausedState.pausedAtParagraph}/${nextPausedState.paragraphTotal} 段，修平后会从后面接着写。`
                : "正文已先停在安全位置，先按右侧建议修一下，再继续往下写。",
            );
            return;
          }

          if (event.event === "done") {
            if (event.text) {
              setDraftText(event.text);
              setDraftDirty(true);
            }
            setPausedStreamState(null);
            setGuardResult(null);
            setStreamStatus(event.message ?? "正文已经顺下来了。");
            setSuccess(
              isResume
                ? "冲突已经修平，正文也从停下的位置接着顺下来了。"
                : "章节初稿已经顺出来了，你可以继续手写，也可以直接优化爽点。",
            );
            return;
          }

          if (event.event === "error") {
            throw new Error(event.message ?? "流式起稿失败。");
          }
        },
      );
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      setStreamStatus(isResume ? "这次续写没接上，请稍后再试。" : "这次起稿没顺下来，请稍后再试。");
    } finally {
      setStreamingChapter(false);
      setActiveRepairInstruction(null);
    }
  }

  async function handleContinueWithRepair(option: string) {
    if (!pausedStreamState) {
      return;
    }
    await handleRunStreamGenerate({
      resumeFromParagraph: pausedStreamState.nextParagraphIndex,
      repairInstruction: option,
      rewriteLatestParagraph: true,
    });
  }

  async function handleContinueAfterManualFix() {
    if (!pausedStreamState) {
      return;
    }
    await handleRunStreamGenerate({
      resumeFromParagraph: pausedStreamState.nextParagraphIndex,
    });
  }

  async function handleRunOptimize(successMessage = "终稿优化完成，右下方可以直接看对比。") {
    setOptimizing(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<FinalOptimizeResponse>(
        `/api/v1/projects/${projectId}/story-engine/workflows/final-optimize`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_id: selectedBranchId,
            chapter_id: activeChapter?.id ?? null,
            chapter_number: chapterNumber,
            chapter_title: chapterTitle || null,
            draft_text: draftText,
            style_sample: styleSample || null,
          }),
        },
      );
      setFinalResult(data);
      const workflowRun = buildWorkflowRunFromTimeline(data.workflow_timeline ?? []);
      if (workflowRun) {
        upsertWorkflowRun(workflowRun);
      }
      setActiveStage("final");
      setPendingStageScroll("final");
      setSuccess(
        data.ready_for_publish
          ? data.quality_summary ?? successMessage
          : data.quality_summary ?? "这轮深度收口还没完全结束，右下方先看问题和优化稿。",
      );
      await loadWorkspace(false, selectedBranchId);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setOptimizing(false);
    }
  }

  async function handleResolveKnowledgeSuggestion(
    suggestion: StoryKnowledgeSuggestion,
    action: "apply" | "ignore",
  ) {
    const summarySource = finalResult?.chapter_summary ?? persistedChapterSummary;
    if (!summarySource) {
      return;
    }
    setResolvingSuggestionId(suggestion.suggestion_id);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiFetchWithAuth<StoryKnowledgeSuggestionResolveResponse>(
        `/api/v1/projects/${projectId}/story-engine/chapter-summaries/${summarySource.summary_id}/kb-updates/${suggestion.suggestion_id}`,
        {
          method: "POST",
          body: JSON.stringify({ action }),
        },
      );
      setFinalResult((current) =>
        applyResolvedSuggestionToFinalResult(current, response.resolved_suggestion),
      );
      setWorkspace((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          chapter_summaries: current.chapter_summaries.map((item) =>
            item.summary_id === response.chapter_summary.summary_id ? response.chapter_summary : item,
          ),
        };
      });
      await loadWorkspace(false, selectedBranchId);
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
      setSuccess(response.message);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setResolvingSuggestionId(null);
    }
  }

  async function handleApplyStyleTemplate(templateKey: string) {
    if (styleActionKey) {
      return;
    }

    setStyleActionKey(`style:apply:${templateKey}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth<UserPreferenceProfile>(
        `/api/v1/profile/style-templates/${templateKey}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ mode: "replace" }),
        },
      );
      await loadStyleControlState(false);
      setSuccess("这套手感已经套进整本书，后面的起稿和优化都会优先按它收束。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStyleActionKey(null);
    }
  }

  async function handleClearStyleTemplate() {
    if (styleActionKey) {
      return;
    }

    setStyleActionKey("style:clear");
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/style-templates/active", {
        method: "DELETE",
      });
      await loadStyleControlState(false);
      setSuccess("当前底稿已经清掉，后续会按你手动保存的长期手感继续走。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStyleActionKey(null);
    }
  }

  async function handleSaveStylePreference(payload: {
    prose_style: string;
    narrative_mode: string;
    pacing_preference: string;
    dialogue_preference: string;
    tension_preference: string;
    sensory_density: string;
    favored_elements: string[];
    banned_patterns: string[];
    custom_style_notes: string | null;
  }) {
    if (styleActionKey) {
      return;
    }

    setStyleActionKey("style:save");
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadStyleControlState(false);
      setSuccess("这套文风手感已经记住，后续章节会尽量稳住这个声音。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStyleActionKey(null);
    }
  }

  function ensureReviewActionChapter() {
    if (!activeChapter) {
      setError("请先把这一章保存成正式章节，再继续做版本和收口动作。");
      return null;
    }
    if (draftDirty) {
      setError("当前正文还有未保存改动，请先保存正文，再继续做这一项。");
      return null;
    }
    return activeChapter;
  }

  async function handleCreateReviewComment(payload: {
    body: string;
    parent_comment_id?: string | null;
    assignee_user_id?: string | null;
    selection_start?: number | null;
    selection_end?: number | null;
    selection_text?: string | null;
  }) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    const actionKey = payload.parent_comment_id
      ? `comment:reply:${payload.parent_comment_id}`
      : "comment:create";
    setReviewSubmittingActionKey(actionKey);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(`/api/v1/chapters/${chapter.id}/comments`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshActiveChapterReviewState(chapter.id);
      setSuccess(
        payload.parent_comment_id
          ? "回复已经挂上去了。"
          : "批注已经记下，后面处理时会一直跟着这章走。",
      );
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleUpdateReviewComment(
    commentId: string,
    payload: {
      status?: string;
      assignee_user_id?: string | null;
    },
  ) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    const actionKey = payload.status
      ? `comment:status:${commentId}:${payload.status}`
      : `comment:assign:${commentId}`;
    setReviewSubmittingActionKey(actionKey);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(`/api/v1/chapters/${chapter.id}/comments/${commentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await refreshActiveChapterReviewState(chapter.id);
      if (payload.status === "resolved") {
        setSuccess("这条批注已经标成解决。");
      } else if (payload.status === "in_progress") {
        setSuccess("这条批注已经挂成处理中。");
      } else if (payload.status === "open") {
        setSuccess("这条批注已经重新挂回待处理。");
      } else {
        setSuccess("负责人已经更新。");
      }
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleDeleteReviewComment(commentId: string) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    const shouldDelete = window.confirm("确认删除这条批注吗？删除后不会自动恢复。");
    if (!shouldDelete) {
      return false;
    }

    setReviewSubmittingActionKey(`comment:delete:${commentId}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(`/api/v1/chapters/${chapter.id}/comments/${commentId}`, {
        method: "DELETE",
      });
      await refreshActiveChapterReviewState(chapter.id);
      setSuccess("这条批注已经删除。");
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleCreateCheckpoint(payload: {
    checkpoint_type: string;
    title: string;
    description?: string | null;
  }) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    setReviewSubmittingActionKey("checkpoint:create");
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(`/api/v1/chapters/${chapter.id}/checkpoints`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshActiveChapterReviewState(chapter.id, {
        refreshChapterChain: true,
      });
      setSuccess("确认点已经挂上，章节状态也同步刷新了。");
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleUpdateCheckpoint(
    checkpointId: string,
    payload: {
      status: string;
      decision_note?: string | null;
    },
  ) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    const actionPrefix =
      payload.status === "approved"
        ? "approve"
        : payload.status === "rejected"
          ? "reject"
          : payload.status;
    setReviewSubmittingActionKey(`checkpoint:${actionPrefix}:${checkpointId}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(
        `/api/v1/chapters/${chapter.id}/checkpoints/${checkpointId}`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
      );
      await refreshActiveChapterReviewState(chapter.id, {
        refreshChapterChain: true,
      });
      setSuccess(
        payload.status === "approved"
          ? "确认点已经通过。"
          : payload.status === "rejected"
            ? "确认点已经驳回。"
            : "确认点已经取消。",
      );
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleCreateReviewDecision(payload: {
    verdict: string;
    summary: string;
    focus_points: string[];
  }) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    setReviewSubmittingActionKey("decision:create");
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(`/api/v1/chapters/${chapter.id}/reviews`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshActiveChapterReviewState(chapter.id, {
        refreshChapterChain: true,
      });
      setSuccess("本章结论已经记下，章节状态也同步更新了。");
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleRollbackVersion(versionId: string, versionNumber: number) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return false;
    }

    const shouldRollback = window.confirm(
      `确认退回到 V${versionNumber} 吗？当前内容不会被抹掉，而是会重新记成一版新的当前稿。`,
    );
    if (!shouldRollback) {
      return false;
    }

    setReviewSubmittingActionKey(`rollback:${versionId}`);
    setError(null);
    setSuccess(null);

    try {
      const response = await apiFetchWithAuth<RollbackResponse>(
        `/api/v1/chapters/${chapter.id}/rollback/${versionId}`,
        {
          method: "POST",
        },
      );
      setChapters((current) =>
        sortChapters([
          ...current.filter((item) => item.id !== response.chapter.id),
          response.chapter,
        ]),
      );
      setDraftText(response.chapter.content);
      setDraftDirty(false);
      await clearCurrentLocalDraft();
      await clearCurrentCloudDraft();
      setFinalResult(null);
      await Promise.all([
        refreshActiveChapterReviewState(chapter.id, {
          refreshChapterChain: true,
        }),
        loadStyleControlState(false),
      ]);
      setSuccess(
        `已经退回到 V${versionNumber} 的内容，并重新记成当前的 V${response.chapter.current_version_number}。`,
      );
      return true;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return false;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleRewriteSelection(payload: {
    selection_start: number;
    selection_end: number;
    instruction: string;
  }) {
    const chapter = ensureReviewActionChapter();
    if (!chapter || reviewSubmittingActionKey) {
      return null;
    }

    setReviewSubmittingActionKey("rewrite-selection");
    setError(null);
    setSuccess(null);

    try {
      const response = await apiFetchWithAuth<ChapterSelectionRewriteResponse>(
        `/api/v1/chapters/${chapter.id}/rewrite-selection`,
        {
          method: "POST",
          body: JSON.stringify({
            ...payload,
            create_version: true,
          }),
        },
      );
      setChapters((current) =>
        sortChapters([
          ...current.filter((item) => item.id !== response.chapter.id),
          response.chapter,
        ]),
      );
      setDraftText(response.chapter.content);
      setDraftDirty(false);
      await clearCurrentLocalDraft();
      await clearCurrentCloudDraft();
      setFinalResult(null);
      await Promise.all([
        refreshActiveChapterReviewState(chapter.id, {
          refreshChapterChain: true,
        }),
        loadStyleControlState(false),
      ]);
      setSuccess(
        `这段已经按你的要求重写完，并记成当前的 V${response.chapter.current_version_number}。`,
      );
      return response;
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      return null;
    } finally {
      setReviewSubmittingActionKey(null);
    }
  }

  async function handleSaveDraft() {
    if (!projectStructure) {
      setError("项目结构还没同步完成，请稍后再试。");
      return;
    }

    setSavingDraft(true);
    setError(null);
    setSuccess(null);

    try {
      const currentOutline =
        outlineList.find((item) => item.level === "level_3" && item.node_order === chapterNumber) ?? null;
      const outlinePayload = buildChapterOutlinePayload(currentOutline);

      if (activeChapter) {
        const payload: Record<string, unknown> = {
          title: chapterTitle.trim() || null,
          content: draftText,
          outline: outlinePayload,
          change_reason: "Saved from story room",
          create_version: true,
        };
        if (activeChapter.status === "draft" && draftText.trim().length > 0) {
          payload.status = "writing";
        }
        const updatedChapter = await apiFetchWithAuth<Chapter>(`/api/v1/chapters/${activeChapter.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setChapters((current) =>
          sortChapters([
            ...current.filter((chapter) => chapter.id !== updatedChapter.id),
            updatedChapter,
          ]),
        );
        setDraftDirty(false);
        await clearCurrentLocalDraft();
        await clearCurrentCloudDraft();
        setSuccess(`第 ${chapterNumber} 章已保存，版本和发布状态都会按这版继续跟进。`);
      } else {
        const createdChapter = await apiFetchWithAuth<Chapter>(
          `/api/v1/projects/${projectId}/chapters`,
          {
            method: "POST",
            body: JSON.stringify({
              chapter_number: chapterNumber,
              volume_id: selectedVolumeId,
              branch_id: selectedBranchId,
              title: chapterTitle.trim() || null,
              content: draftText,
              outline: outlinePayload,
              status: draftText.trim().length > 0 ? "writing" : "draft",
              change_reason: "Created from story room",
            }),
          },
        );
        setChapters((current) => sortChapters([...current, createdChapter]));
        setDraftDirty(false);
        await clearCurrentLocalDraft();
        await clearCurrentCloudDraft();
        setSuccess(`第 ${chapterNumber} 章已经存成正式章节，后续修改都会留下版本记录。`);
      }

      await Promise.all([refreshChapterChainState(), loadStyleControlState(false)]);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setSavingDraft(false);
    }
  }

  function handleApplyOptimizedDraft() {
    if (!finalResult) {
      setError("当前还没有可采纳的优化稿。");
      return;
    }

    if (finalResult.final_draft === draftText) {
      setSuccess("优化稿已经在正文里了，可以直接继续微调。");
      return;
    }

    setDraftText(finalResult.final_draft);
    setDraftDirty(true);
    setSuccess("优化稿已经带回正文编辑区了，确认无误后记得保存正文。");
  }

  async function handleSaveAsFinal(options: { continueToNextChapter?: boolean } = {}) {
    const { continueToNextChapter = false } = options;
    if (!activeChapter) {
      setError("请先把这一章保存成正式章节，再尝试放行。");
      return;
    }
    if (draftDirty) {
      setError("当前还有未保存改动，请先保存正文，再尝试放行。");
      return;
    }

    setFinalizingAction(continueToNextChapter ? "continue" : "save");
    setError(null);
    setSuccess(null);

    try {
      const updatedChapter = await apiFetchWithAuth<Chapter>(`/api/v1/chapters/${activeChapter.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "final",
          change_reason: "Marked as final from story room",
          create_version: false,
        }),
      });
      await clearCurrentCloudDraft();

      setChapters((current) =>
        sortChapters([
          ...current.filter((chapter) => chapter.id !== updatedChapter.id),
          updatedChapter,
        ]),
      );
      const [{ chapterData }, bootstrapData] = await Promise.all([
        refreshChapterChainState(),
        loadProjectBootstrap({ branchId: selectedBranchId }),
      ]);

      const nextScopeChapters = chapterData.filter((chapter) =>
        isChapterInScope(chapter, selectedBranchId, selectedVolumeId),
      );
      const resolvedNextChapter = resolveNextChapterCandidate({
        bootstrapCandidate: bootstrapData?.next_chapter ?? null,
        currentChapterId: updatedChapter.id,
        currentChapterNumber: updatedChapter.chapter_number,
        branchId: selectedBranchId,
        branchTitle: selectedBranchTitle,
        volumeId: selectedVolumeId,
        volumeTitle: selectedVolumeTitle,
        scopeChapters: nextScopeChapters,
        level3Outlines: level3OutlineList,
      });

      if (continueToNextChapter) {
        openNextChapterDraft(resolvedNextChapter, { afterFinalize: true });
        return;
      }

      setSuccess(
        updatedChapter.status === "final"
          ? "这章已经标记为终稿状态，章节总结和设定沉淀会继续服务下一章。"
          : "终稿状态已经刷新。",
      );
    } catch (requestError) {
      let latestGateReason = activeChapter.final_gate_reason;

      try {
        const { chapterData } = await refreshChapterChainState();
        const latestChapter = chapterData.find((chapter) => chapter.id === activeChapter.id);
        latestGateReason = latestChapter?.final_gate_reason ?? latestGateReason;
      } catch {
        // 放行失败时，优先保留原始错误，让页面至少能给出明确反馈。
      }

      setError(latestGateReason ?? buildUserFriendlyError(requestError));
    } finally {
      setFinalizingAction(null);
    }
  }

  async function handleExportChapter(format: "md" | "txt") {
    if (!activeChapter) {
      setError("请先把这一章保存成正式章节，再导出交稿版。");
      return;
    }
    if (draftDirty) {
      setError("当前还有未保存改动，请先保存正文，再导出交稿版。");
      return;
    }

    setExportingFormat(format);
    setError(null);
    setSuccess(null);

    try {
      const { downloadWithAuth } = await import("@/lib/api");
      await downloadWithAuth(`/api/v1/chapters/${activeChapter.id}/export?format=${format}`);
      setSuccess(format === "md" ? "Markdown 交稿版已经开始导出。" : "TXT 交稿版已经开始导出。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setExportingFormat(null);
    }
  }

  async function handleApproveStoryBiblePendingChange(changeId: string) {
    if (storyBibleGovernanceActionKey) {
      return;
    }
    setStoryBibleGovernanceActionKey(`pending:approve:${changeId}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(
        `/api/v1/projects/${projectId}/bible/pending-changes/${changeId}/approve`,
        {
          method: "POST",
          body: JSON.stringify({
            approved: true,
            comment: null,
          }),
        },
      );
      await Promise.all([
        loadWorkspace(false, selectedBranchId),
        loadStoryBibleGovernanceState(storyBibleBranchId, false),
      ]);
      setSuccess("这条自动记设定已经确认收入圣经。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStoryBibleGovernanceActionKey(null);
    }
  }

  async function handleRejectStoryBiblePendingChange(changeId: string) {
    if (storyBibleGovernanceActionKey) {
      return;
    }

    const reason = window.prompt("给这条设定建议留一句退回原因：", "");
    if (reason === null) {
      return;
    }
    if (!reason.trim()) {
      setError("退回设定建议时，需要写一句原因。");
      return;
    }

    setStoryBibleGovernanceActionKey(`pending:reject:${changeId}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(
        `/api/v1/projects/${projectId}/bible/pending-changes/${changeId}/reject`,
        {
          method: "POST",
          body: JSON.stringify({
            approved: false,
            comment: reason.trim(),
          }),
        },
      );
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
      setSuccess("这条自动记设定已经退回，不会直接收入圣经。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStoryBibleGovernanceActionKey(null);
    }
  }

  async function handleRollbackStoryBibleVersion(versionId: string, versionNumber: number) {
    if (storyBibleGovernanceActionKey) {
      return;
    }

    const shouldRollback = window.confirm(
      `确认退回到设定 V${versionNumber} 吗？当前圣经会按那一版恢复，并重新记成一条新版本。`,
    );
    if (!shouldRollback) {
      return;
    }

    const reason = window.prompt("这次设定回退想留一句原因吗？可留空。", "") ?? "";
    setStoryBibleGovernanceActionKey(`version:rollback:${versionId}`);
    setError(null);
    setSuccess(null);

    try {
      await apiFetchWithAuth(
        `/api/v1/projects/${projectId}/bible/rollback${
          storyBibleBranchId ? `?branch_id=${encodeURIComponent(storyBibleBranchId)}` : ""
        }`,
        {
          method: "POST",
          body: JSON.stringify({
            target_version_id: versionId,
            reason: reason.trim() || null,
          }),
        },
      );
      await Promise.all([
        loadWorkspace(false, selectedBranchId),
        loadStoryBibleGovernanceState(storyBibleBranchId, false),
      ]);
      setSuccess(`设定圣经已经退回到 V${versionNumber} 对应的版本。`);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setStoryBibleGovernanceActionKey(null);
    }
  }

  async function handleKnowledgeSave() {
    setSavingKnowledge(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = buildKnowledgePayload(activeTab, formState, editingId);
      const branchId = isStoryBibleKnowledgeTab(activeTab)
        ? storyBibleBranchId
        : null;

      if (isStoryBibleKnowledgeTab(activeTab) && !branchId) {
        throw new Error("当前项目还没有默认主线，暂时不能保存这类设定。");
      }

      const result = await apiFetchWithAuth<StoryKnowledgeMutationResponse>(
        `/api/v1/projects/${projectId}/story-engine/knowledge/${activeTab}`,
        {
          method: "POST",
          body: JSON.stringify({
            entity_id: editingId,
            branch_id: branchId,
            previous_entity_key: isStoryBibleKnowledgeTab(activeTab) ? editingId : null,
            item: payload,
          }),
        },
      );

      setEditingId(null);
      setFormState({});
      setSuccess(result.message);
      await loadWorkspace(false, selectedBranchId);
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setSavingKnowledge(false);
    }
  }

  async function handleDeleteKnowledge(tab: KnowledgeTabKey, entityId: string) {
    setError(null);
    setSuccess(null);
    try {
      const branchId = isStoryBibleKnowledgeTab(tab)
        ? storyBibleBranchId
        : null;
      if (isStoryBibleKnowledgeTab(tab) && !branchId) {
        throw new Error("当前项目还没有默认主线，暂时不能删除这类设定。");
      }

      const result = await apiFetchWithAuth<StoryKnowledgeMutationResponse>(
        `/api/v1/projects/${projectId}/story-engine/knowledge/${tab}/remove`,
        {
          method: "POST",
          body: JSON.stringify({
            entity_id: entityId,
            branch_id: branchId,
          }),
        },
      );
      setSuccess(result.message);
      await loadWorkspace(false, selectedBranchId);
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    }
  }

  async function runKnowledgeSearch(query: string, options: { autoLocate?: boolean } = {}) {
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      setSearchResults([]);
      return;
    }
    try {
      const data = await apiFetchWithAuth<StorySearchResult[]>(
        `/api/v1/projects/${projectId}/story-engine/search?query=${encodeURIComponent(normalizedQuery)}`,
      );
      setSearchResults(data);
      if (options.autoLocate && data.length > 0) {
        const firstMatchedTab = resolveKnowledgeTabForEntityType(data[0].entity_type);
        if (firstMatchedTab) {
          setActiveTab(firstMatchedTab);
          setHighlightedKnowledgeId(data[0].entity_id);
        }
      }
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    }
  }

  async function handleSearch() {
    await runKnowledgeSearch(searchQuery);
  }

  async function handleLocateKnowledgeFromSelection(selectionText: string) {
    const query = selectionText.trim();
    if (!query) {
      setError("先在正文里选中人物、物品或规则，再去设定里定位。");
      return;
    }

    setError(null);
    setSuccess(null);
    setSearchQuery(query);
    openStage("knowledge");
    setPendingStageScroll("knowledge");

    const normalizedQuery = normalizeKnowledgeLookupText(query);
    const localMatch =
      knowledgeLookupEntries.find((item) => item.normalizedLabel === normalizedQuery) ??
      knowledgeLookupEntries.find(
        (item) =>
          item.normalizedLabel.includes(normalizedQuery) ||
          normalizedQuery.includes(item.normalizedLabel),
      ) ??
      null;

    if (localMatch) {
      setActiveTab(localMatch.tab);
      setHighlightedKnowledgeId(localMatch.itemId);
      setSearchResults([]);
      setSuccess(`已在设定里定位到「${localMatch.label}」。`);
      return;
    }

    await runKnowledgeSearch(query, { autoLocate: true });
    setSuccess(`已把“${query}”带到设定区，你可以继续查看相关条目。`);
  }

  function handleLocateSearchResult(result: StorySearchResult) {
    const tab = resolveKnowledgeTabForEntityType(result.entity_type);
    if (!tab) {
      setError("这条搜索结果暂时不能直接定位到设定卡片。");
      return;
    }

    setActiveTab(tab);
    setHighlightedKnowledgeId(result.entity_id);
    setSuccess("已定位到对应设定条目。");
  }

  function handleJumpToRelatedChapter(tab: KnowledgeTabKey, item: Record<string, unknown>) {
    const itemLabel = resolveKnowledgeItemLabel(tab, item) || "这条设定";
    const draftMatch =
      itemLabel &&
      itemLabel.length > 0 &&
      draftText.includes(itemLabel)
        ? chapterNumber
        : null;
    const directChapter =
      tab === "foreshadows"
        ? Number(item.chapter_planted ?? item.chapter_planned_reveal ?? 0) || null
        : tab === "timeline_events"
          ? Number(item.chapter_number ?? 0) || null
          : null;
    const matchedChapter =
      directChapter ??
      draftMatch ??
      (itemLabel
        ? scopeChapters.find((chapter) => {
            const chapterTitleText = chapter.title?.trim() ?? "";
            return (
              chapter.content.includes(itemLabel) ||
              chapterTitleText.includes(itemLabel)
            );
          })?.chapter_number ??
          null
        : null);

    if (!matchedChapter) {
      setError(`暂时还没在正文里定位到「${itemLabel}」对应的章节。`);
      return;
    }

    openStage("draft");
    setPendingStageScroll("draft");
    handleJumpToChapter(matchedChapter);
    setSuccess(`已跳到第 ${matchedChapter} 章查看「${itemLabel}」相关正文。`);
  }

  function handleImportTemplateChange(value: string) {
    setSelectedTemplateKey(value);
    if (!value) {
      return;
    }
    const template = importTemplates.find((item) => item.key === value);
    if (!template) {
      return;
    }
    setImportPayloadText(JSON.stringify(template.payload, null, 2));
    setReplaceSections(DEFAULT_IMPORT_REPLACE_SECTIONS);
  }

  function handleToggleReplaceSection(section: string) {
    setReplaceSections((current) =>
      current.includes(section)
        ? current.filter((item) => item !== section)
        : [...current, section],
    );
  }

  async function handleSubmitImport() {
    setImportingKnowledge(true);
    setError(null);
    setSuccess(null);

    try {
      const parsedPayload = JSON.parse(importPayloadText) as Record<string, unknown>;
      const data = await apiFetchWithAuth<StoryBulkImportResponse>(
        `/api/v1/projects/${projectId}/story-engine/imports/bulk`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_id: selectedBranchId,
            template_key: selectedTemplateKey || null,
            apply_template_model_routing: false,
            replace_existing_sections: replaceSections,
            payload: parsedPayload,
          }),
        },
      );
      setStressResult(null);
      const workflowRun = buildWorkflowRunFromTimeline(data.workflow_timeline ?? []);
      if (workflowRun) {
        upsertWorkflowRun(workflowRun);
      }
      setSuccess(buildImportSummary(data));
      await Promise.all([
        loadWorkspace(false, selectedBranchId),
        loadStoryBibleGovernanceState(storyBibleBranchId, false),
        loadProjectTaskPlayback(),
      ]);
    } catch (requestError) {
      if (requestError instanceof SyntaxError) {
        setError("设定包格式看起来不完整，请检查逗号、括号和引号。");
      } else {
        setError(buildUserFriendlyError(requestError));
      }
    } finally {
      setImportingKnowledge(false);
    }
  }

  async function handleGenerateSuggestion(kind: KnowledgeSuggestionKind) {
    setDispatchingEntityKind(kind);
    setError(null);
    setSuccess(null);

    const payload =
      kind === "characters"
        ? {
            character_type: "supporting",
            count: 3,
            genre: workspace?.project.genre ?? null,
            tone: workspace?.project.tone ?? null,
            theme: workspace?.project.theme ?? null,
            existing_characters:
              workspace?.characters.map((item) => item.name).join(", ") || null,
          }
        : kind === "items"
          ? {
              item_type: "artifact",
              count: 3,
              genre: workspace?.project.genre ?? null,
              tone: workspace?.project.tone ?? null,
              existing_items: workspace?.items.map((item) => item.name).join(", ") || null,
            }
          : kind === "locations"
            ? {
                location_type: "city",
                count: 2,
                genre: workspace?.project.genre ?? null,
                tone: workspace?.project.tone ?? null,
              }
            : kind === "factions"
              ? {
                  faction_type: "guild",
                  count: 1,
                  genre: workspace?.project.genre ?? null,
                  tone: workspace?.project.tone ?? null,
                }
              : {
                  plot_type: "sub",
                  count: 2,
                  genre: workspace?.project.genre ?? null,
                  tone: workspace?.project.tone ?? null,
                };

    try {
      const data = await apiFetchWithAuth<ProjectEntityGenerationDispatch>(
        `/api/v1/projects/${projectId}/generations/${ENTITY_GENERATION_ENDPOINTS[kind]}/dispatch`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setEntityTaskState(data.task);
      await loadEntityTaskEvents(data.task.task_id);
      await loadProjectTaskPlayback();
      setSuccess(`已经开始补${ENTITY_GENERATION_SUCCESS_LABELS[kind]}，结果会挂在右侧。`);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setDispatchingEntityKind(null);
    }
  }

  async function handleAcceptSuggestion(candidateIndex: number) {
    if (!entityTaskState) {
      setError("当前没有可采纳的补全结果。");
      return;
    }

    const shouldAccept = window.confirm("确认把这条候选直接收入当前设定库吗？");
    if (!shouldAccept) {
      return;
    }

    setAcceptingCandidateIndex(candidateIndex);
    setError(null);
    setSuccess(null);

    try {
      const data = await apiFetchWithAuth<StoryGeneratedCandidateAcceptResponse>(
        `/api/v1/projects/${projectId}/story-engine/generated-candidates/accept`,
        {
          method: "POST",
          body: JSON.stringify({
            task_id: entityTaskState.task_id,
            candidate_index: candidateIndex,
            branch_id: storyBibleBranchId,
          }),
        },
      );

      setEntityTaskState((current) => {
        if (!current?.result) {
          return current;
        }
        const generationType =
          typeof current.result.generation_type === "string"
            ? current.result.generation_type
            : null;
        if (!generationType) {
          return current;
        }
        const resultKey = generationType === "supporting" ? "characters" : generationType;
        const rawCandidates = current.result[resultKey];
        if (!Array.isArray(rawCandidates)) {
          return current;
        }
        const nextCandidates = rawCandidates.filter((_, index) => index !== candidateIndex);
        return {
          ...current,
          result: {
            ...current.result,
            [resultKey]: nextCandidates,
            candidate_count: nextCandidates.length,
            entity_preview: nextCandidates
              .slice(0, 5)
              .map((item) =>
                item && typeof item === "object"
                  ? String((item as Record<string, unknown>).name ?? (item as Record<string, unknown>).title ?? "").trim()
                  : "",
              )
              .filter(Boolean),
          },
        };
      });

      await loadWorkspace(false, selectedBranchId);
      if (
        data.accepted_entity_type === "characters" ||
        data.accepted_entity_type === "items" ||
        data.accepted_entity_type === "locations" ||
        data.accepted_entity_type === "factions" ||
        data.accepted_entity_type === "plot_threads"
      ) {
        setActiveTab(data.accepted_entity_type);
      }
      setHighlightedKnowledgeId(
        data.accepted_entity_key ?? (data.accepted_entity_id ? String(data.accepted_entity_id) : null),
      );
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
      setSuccess(data.message);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setAcceptingCandidateIndex(null);
    }
  }

  function handleStartEdit(tab: KnowledgeTabKey, item: Record<string, unknown>) {
    setActiveTab(tab);
    setEditingId(resolveKnowledgeEntityId(tab, item));
    setFormState(buildEditForm(tab, item));
  }

  function handleKnowledgeTabChange(tab: KnowledgeTabKey) {
    setActiveTab(tab);
    setEditingId(null);
    setFormState({});
  }

  function handleCancelEdit() {
    setEditingId(null);
    setFormState({});
  }

  if (loading) {
    return (
      <main className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-7xl rounded-[36px] border border-black/10 bg-white/75 p-10 text-sm text-black/55">
          正在装载你的故事工作台...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-8 pb-40 md:px-6 md:pb-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-[42px] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)] md:p-8">
          <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-copper">写作现场</p>
              <h1 className="mt-2 text-3xl font-semibold">{workspace?.project.title}</h1>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                  题材：{workspace?.project.genre ?? genre ?? "未填写"}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                  气质：{workspace?.project.tone ?? tone ?? "未填写"}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                  设定条目：{knowledgeItemCount}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                  当前章节：第 {chapterNumber} 章
                </span>
              </div>

              <section className="mt-6 rounded-[28px] border border-copper/20 bg-[#fff7ef] p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-copper">下一步</p>
                    <h2 className="mt-2 text-xl font-semibold">{recommendedStageCard.title}</h2>
                    <p className="mt-2 hidden text-sm leading-7 text-black/58 md:block">
                      {recommendedStageSummaryMap[recommendedStageCard.key]}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2 md:hidden">
                      <span className="rounded-full border border-copper/20 bg-white px-3 py-1 text-xs text-copper">
                        当前推荐
                      </span>
                      <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                        {recommendedStageSummaryMap[recommendedStageCard.key]}
                      </span>
                    </div>
                  </div>
                  <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap">
                    <button
                      className="w-full rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 sm:w-auto"
                      onClick={handlePrimaryStageAction}
                      type="button"
                    >
                      {primaryStageActionLabelMap[recommendedStageCard.key]}
                    </button>
                    <Link
                      className="inline-flex w-full items-center justify-center rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] sm:w-auto"
                      href={`/dashboard/projects/${projectId}/collaborators`}
                    >
                      协作成员
                    </Link>
                    <Link
                      className="inline-flex w-full items-center justify-center rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] sm:w-auto"
                      href="/dashboard"
                    >
                      返回项目总览
                    </Link>
                  </div>
                </div>

                <div className="mt-5 hidden gap-3 md:grid md:grid-cols-2 xl:grid-cols-4">
                  {stageCards.map((card, index) => {
                    const isActive = activeStageValue === card.key;
                    const isRecommended = recommendedStage === card.key;
                    return (
                      <button
                        key={card.key}
                        className={`rounded-[22px] border px-4 py-4 text-left transition ${
                          isActive
                            ? "border-copper/30 bg-white shadow-[0_14px_30px_rgba(176,112,53,0.1)]"
                            : "border-black/10 bg-white/80 hover:bg-white"
                        }`}
                        onClick={() => openStage(card.key)}
                        type="button"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-black/10 bg-[#fbfaf5] text-xs font-semibold text-black/62">
                            {index + 1}
                          </span>
                          {isRecommended ? (
                            <span className="rounded-full border border-copper/20 bg-[#fff7ef] px-3 py-1 text-xs text-copper">
                              当前
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-3 text-sm font-semibold">{card.title}</p>
                        <p className="mt-2 text-xs text-black/52">{card.status}</p>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-5 flex gap-2 overflow-x-auto pb-1 md:hidden">
                  {stageCards.map((card) => {
                    const isActive = activeStageValue === card.key;
                    return (
                      <button
                        key={`mobile-stage-card-${card.key}`}
                        className={`min-w-[110px] rounded-[18px] border px-3 py-3 text-left transition ${
                          isActive
                            ? "border-copper/30 bg-white shadow-[0_12px_24px_rgba(176,112,53,0.1)]"
                            : "border-black/10 bg-white/80"
                        }`}
                        onClick={() => openStage(card.key)}
                        type="button"
                      >
                        <p className="text-sm font-semibold text-black/82">{card.title}</p>
                        <p className="mt-1 text-[11px] text-black/52">{card.status}</p>
                      </button>
                    );
                  })}
                </div>
              </section>
            </div>

            <div className="space-y-4">
              <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
                <p className="text-sm font-semibold">{isDraftFocusMode ? "当前在写" : "当前范围"}</p>
                <h2 className="mt-3 text-2xl font-semibold">
                  {isDraftFocusMode
                    ? chapterTitle.trim().length > 0
                      ? `第 ${chapterNumber} 章 · ${chapterTitle.trim()}`
                      : `第 ${chapterNumber} 章`
                    : scopeLabel}
                </h2>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    {currentOutline ? `已挂第 ${currentOutline.node_order} 章章纲` : "待挂章纲"}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    已存 {savedChapterCount} 章
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    目标 {effectiveTargetChapterCount} 章
                  </span>
                  {hasOptimizationResult ? (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                      已有终稿结果
                    </span>
                  ) : null}
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                    onClick={() => openStage("outline")}
                    type="button"
                  >
                    回章纲
                  </button>
                  {!hasDraftStarted && hasOutlineBlueprint ? (
                    <button
                      className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                      onClick={openDraftFromOutline}
                      type="button"
                    >
                      去写第一章
                    </button>
                  ) : null}
                  {hasDraftStarted && !isDraftFocusMode ? (
                    <button
                      className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                      onClick={() => openStage("draft")}
                      type="button"
                    >
                      回正文区
                    </button>
                  ) : null}
                  {hasOptimizationResult ? (
                    <button
                      className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                      onClick={() => openStage("final")}
                      type="button"
                    >
                      看终稿结果
                    </button>
                  ) : null}
                </div>
              </section>

              <div className="hidden md:block">
                <StoryScopeSwitcher
                  branches={projectStructure?.branches ?? []}
                  volumes={projectStructure?.volumes ?? []}
                  selectedBranchId={selectedBranchId}
                  selectedVolumeId={selectedVolumeId}
                  chapterCount={savedChapterCount}
                  pendingChangeCount={storyBiblePendingChanges.length}
                  scopeChapters={scopeChapters}
                  activeChapterNumber={chapterNumber}
                  actionKey={scopeActionKey}
                  onSelectBranchId={handleSelectBranchId}
                  onSelectVolumeId={handleSelectVolumeId}
                  onJumpToChapter={handleJumpToChapter}
                  onCreateBranch={handleCreateBranch}
                  onUpdateBranch={handleUpdateBranch}
                  onCreateVolume={handleCreateVolume}
                  onUpdateVolume={handleUpdateVolume}
                />
              </div>

              <details className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5 md:hidden">
                <summary className="cursor-pointer list-none text-base font-semibold text-black/82">
                  卷线与章节范围
                </summary>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    {selectedBranchTitle}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    {selectedVolumeTitle}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    已存 {savedChapterCount} 章
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                    待确认 {storyBiblePendingChanges.length} 条
                  </span>
                </div>
                <div className="mt-4">
                  <StoryScopeSwitcher
                    branches={projectStructure?.branches ?? []}
                    volumes={projectStructure?.volumes ?? []}
                    selectedBranchId={selectedBranchId}
                    selectedVolumeId={selectedVolumeId}
                    chapterCount={savedChapterCount}
                    pendingChangeCount={storyBiblePendingChanges.length}
                    scopeChapters={scopeChapters}
                    activeChapterNumber={chapterNumber}
                    actionKey={scopeActionKey}
                    onSelectBranchId={handleSelectBranchId}
                    onSelectVolumeId={handleSelectVolumeId}
                    onJumpToChapter={handleJumpToChapter}
                    onCreateBranch={handleCreateBranch}
                    onUpdateBranch={handleUpdateBranch}
                    onCreateVolume={handleCreateVolume}
                    onUpdateVolume={handleUpdateVolume}
                  />
                </div>
              </details>
            </div>
          </div>

          {error ? (
            <div className="mt-5 rounded-3xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="mt-5 rounded-3xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {success}
            </div>
          ) : null}
        </section>

        <ProcessPlaybackPanel
          title="刚刚发生了什么"
          subtitle="这里会把正文生成、检查收口和自动补设定收成一条线，方便你快速回看。"
          items={playbackItems}
          emptyTitle="最近还没有过程记录"
          emptyDescription="开始起稿、检查正文或补设定后，这里会自动记下最近几步。"
        />

        {activeStageValue === "outline" ? (
          <section id="story-stage-outline" className="scroll-mt-6 space-y-4">
            <div className="flex items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-5 py-4 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-copper">第一步</p>
                <h2 className="mt-1 text-xl font-semibold">生成三级大纲</h2>
              </div>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                输入想法 / 上传大纲
              </span>
            </div>

            <OutlineWorkbench
              outlines={workspace?.outlines ?? []}
              result={stressResult}
              idea={idea}
              genre={genre}
              tone={tone}
              sourceMaterial={sourceMaterial}
              sourceMaterialName={sourceMaterialName}
              targetChapterWords={targetChapterWords}
              targetTotalWords={targetTotalWords}
              estimatedChapterCount={effectiveTargetChapterCount}
              loading={stressLoading}
              savingGoalProfile={savingStoryGoals}
              updatingOutlineId={updatingOutlineId}
              onIdeaChange={setIdea}
              onGenreChange={setGenre}
              onToneChange={setTone}
              onSourceMaterialChange={handleSourceMaterialChange}
              onClearSourceMaterial={handleClearSourceMaterial}
              onTargetChapterWordsChange={setTargetChapterWords}
              onTargetTotalWordsChange={setTargetTotalWords}
              onSaveGoalProfile={() => void handleSaveStoryGoals()}
              onRunStressTest={handleRunStressTest}
              onUpdateOutline={(outlineId, payload) => void handleUpdateOutline(outlineId, payload)}
              onOpenDraftStep={openDraftFromOutline}
            />
          </section>
        ) : null}

        {activeStageValue === "draft" ? (
          <section id="story-stage-draft" className="scroll-mt-6 space-y-4">
            <DraftStudio
              chapterNumber={chapterNumber}
              chapterTitle={chapterTitle}
              draftText={draftText}
              outlines={outlineList}
              scopeChapters={scopeChapters}
              outlineSelectionId={currentOutline?.outline_id ?? null}
              activeChapter={activeChapter}
              scopeLabel={scopeLabel}
              savedChapterCount={savedChapterCount}
              guardResult={guardResult}
              pausedStreamState={pausedStreamState}
              activeRepairInstruction={activeRepairInstruction}
              finalResult={finalResult}
              checkingGuard={checkingGuard}
              streaming={streamingChapter}
              streamStatus={streamStatus}
              optimizing={optimizing}
              savingDraft={savingDraft}
              draftDirty={draftDirty}
              isOnline={isOnline}
              localDraftSavedAt={localDraftSavedAt}
              localDraftRecoveredAt={localDraftRecoveredAt}
              pendingLocalDraftUpdatedAt={pendingLocalDraftSnapshot?.updatedAt ?? null}
              pendingLocalDraftRecoveryState={pendingLocalDraftRecoveryState}
              cloudDraftSavedAt={cloudDraftSavedAt}
              cloudDraftRecoveredAt={cloudDraftRecoveredAt}
              pendingCloudDraftUpdatedAt={pendingCloudDraftSnapshot?.updated_at ?? null}
              pendingCloudDraftRecoveryState={pendingCloudDraftRecoveryState}
              cloudSyncing={cloudSyncing}
              cloudSyncEnabled={isOnline}
              recoverableDrafts={recoverableDraftCards}
              editorRef={editorRef}
              onChapterNumberChange={handleChapterNumberChange}
              onChapterTitleChange={handleChapterTitleInput}
              onDraftTextChange={handleDraftTextInput}
              onSelectOutlineId={handleSelectOutlineId}
              onJumpToChapter={handleJumpToChapter}
              onSaveDraft={() => void handleSaveDraft()}
              onRunStreamGenerate={() => void handleRunStreamGenerate()}
              onContinueWithRepair={(option) => void handleContinueWithRepair(option)}
              onContinueAfterManualFix={() => void handleContinueAfterManualFix()}
              onRunGuardCheck={() => void triggerGuardCheck(true)}
              onRunOptimize={() => void handleRunOptimize()}
              onLocateSelectionInKnowledge={(selectionText) =>
                void handleLocateKnowledgeFromSelection(selectionText)
              }
              onOpenOutlineStep={() => openStage("outline")}
              onOpenFinalStep={() => openStage("final")}
              onOpenReviewTool={openReviewTool}
              onOpenRecoverableDraft={handleOpenRecoverableDraft}
              onRestoreLocalDraft={handleRestoreLocalDraft}
              onDismissLocalDraft={handleDismissLocalDraft}
              onRestoreCloudDraft={handleRestoreCloudDraft}
              onDismissCloudDraft={handleDismissCloudDraft}
            />

            <section
              ref={reviewPanelRef}
              id="story-stage-review-tools"
              className="scroll-mt-6 hidden space-y-4 md:block"
            >
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-4 py-3 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                    精修台
                  </span>
                  <h2 className="text-lg font-semibold">片段改写、批注、版本回退</h2>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                    版本 {chapterVersions.length}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                    批注 {reviewWorkspace?.open_comment_count ?? 0}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                    确认点 {reviewWorkspace?.pending_checkpoint_count ?? 0}
                  </span>
                </div>
              </div>

              <ChapterReviewPanel
                activeChapter={activeChapter}
                draftText={draftText}
                draftDirty={draftDirty}
                reviewWorkspace={reviewWorkspace}
                chapterVersions={chapterVersions}
                loading={loadingChapterReview}
                submittingActionKey={reviewSubmittingActionKey}
                editorRef={editorRef}
                onCreateComment={handleCreateReviewComment}
                onUpdateComment={handleUpdateReviewComment}
                onDeleteComment={handleDeleteReviewComment}
                onCreateCheckpoint={handleCreateCheckpoint}
                onUpdateCheckpoint={handleUpdateCheckpoint}
                onCreateDecision={handleCreateReviewDecision}
                onRollback={handleRollbackVersion}
                onRewriteSelection={handleRewriteSelection}
              />
            </section>

            <details className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)] md:hidden">
              <summary className="cursor-pointer list-none text-lg font-semibold">
                精修台
              </summary>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  版本 {chapterVersions.length}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  批注 {reviewWorkspace?.open_comment_count ?? 0}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  确认点 {reviewWorkspace?.pending_checkpoint_count ?? 0}
                </span>
              </div>
              <div className="mt-4">
                <ChapterReviewPanel
                  activeChapter={activeChapter}
                  draftText={draftText}
                  draftDirty={draftDirty}
                  reviewWorkspace={reviewWorkspace}
                  chapterVersions={chapterVersions}
                  loading={loadingChapterReview}
                  submittingActionKey={reviewSubmittingActionKey}
                  editorRef={editorRef}
                  onCreateComment={handleCreateReviewComment}
                  onUpdateComment={handleUpdateReviewComment}
                  onDeleteComment={handleDeleteReviewComment}
                  onCreateCheckpoint={handleCreateCheckpoint}
                  onUpdateCheckpoint={handleUpdateCheckpoint}
                  onCreateDecision={handleCreateReviewDecision}
                  onRollback={handleRollbackVersion}
                  onRewriteSelection={handleRewriteSelection}
                />
              </div>
            </details>

            <details className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <summary className="cursor-pointer list-none text-lg font-semibold">
                文风与写法控制
              </summary>
              <div className="mt-5">
                <StyleControlPanel
                  mode="story-room"
                  chapterSample={styleSample}
                  secondaryActionHref={`/dashboard/preferences?projectId=${projectId}`}
                  secondaryActionLabel="去风格中心细调"
                  preferenceProfile={preferenceProfile}
                  styleTemplates={styleTemplates}
                  loading={loadingStyleControl}
                  actionKey={styleActionKey}
                  onChapterSampleChange={setStyleSample}
                  onApplyTemplate={(templateKey) => void handleApplyStyleTemplate(templateKey)}
                  onClearTemplate={() => void handleClearStyleTemplate()}
                  onSavePreference={(payload) => void handleSaveStylePreference(payload)}
                />
              </div>
            </details>
          </section>
        ) : null}

        {activeStageValue === "final" ? (
          <section id="story-stage-final" className="scroll-mt-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-4 py-3 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  第三步
                </span>
                <h2 className="text-lg font-semibold">终稿</h2>
                <span
                  className={`rounded-full border px-3 py-1 text-xs ${
                    visibleFinalResult
                      ? visibleFinalResult.ready_for_publish
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-black/10 bg-[#fbfaf5] text-black/60"
                  }`}
                >
                  {visibleFinalResult
                    ? visibleFinalResult.ready_for_publish
                      ? "可以交稿"
                      : "还要确认"
                    : "还没出结果"}
                </span>
              </div>
              {!visibleFinalResult ? (
                <button
                  className="rounded-full bg-copper px-4 py-2 text-sm font-semibold text-white"
                  onClick={() => openStage("draft")}
                  type="button"
                >
                  回正文区继续
                </button>
              ) : null}
            </div>

            <FinalDiffViewer
              result={visibleFinalResult}
              hasDraftText={draftText.trim().length > 0}
              hasSavedChapter={activeChapter !== null}
              chapterTitle={chapterTitle}
              resolvingSuggestionId={resolvingSuggestionId}
              onOpenDraftStep={() => openStage("draft")}
              onApplyKnowledgeSuggestion={(suggestion) =>
                void handleResolveKnowledgeSuggestion(suggestion, "apply")
              }
              onIgnoreKnowledgeSuggestion={(suggestion) =>
                void handleResolveKnowledgeSuggestion(suggestion, "ignore")
              }
            />

            <FinalPublishPanel
              activeChapter={activeChapter}
              draftDirty={draftDirty}
              finalResult={finalResult}
              nextChapter={nextChapterCandidate}
              carryoverPreview={currentChapterCarryoverPreview}
              pendingKnowledgeCount={
                visibleFinalResult?.kb_update_list.filter(
                  (item) => (item.status ?? "pending") === "pending",
                ).length ?? 0
              }
              exportingFormat={exportingFormat}
              finalizingChapter={finalizingChapter}
              finalizingAction={finalizingAction}
              canApplyOptimizedDraft={canApplyOptimizedDraft}
              onOpenDraftStep={() => openStage("draft")}
              onApplyOptimizedDraft={() => handleApplyOptimizedDraft()}
              onSaveAsFinal={() => void handleSaveAsFinal()}
              onSaveAsFinalAndContinue={() =>
                void handleSaveAsFinal({ continueToNextChapter: true })
              }
              onContinueToNextChapter={() => openNextChapterDraft(nextChapterCandidate)}
              onExport={(format) => void handleExportChapter(format)}
            />
          </section>
        ) : null}

        {activeStageValue === "knowledge" ? (
          <section id="story-stage-knowledge" className="scroll-mt-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-4 py-3 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  第四步
                </span>
                <h2 className="text-lg font-semibold">设定</h2>
              </div>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                待确认 {storyBiblePendingChanges.length} 条
              </span>
            </div>

            <KnowledgeBaseBoard
              workspace={workspace}
              storyBible={storyBible}
              activeTab={activeTab}
              highlightedItemId={highlightedKnowledgeId}
              editingId={editingId}
              formState={formState}
              saving={savingKnowledge}
              importing={importingKnowledge}
              searchQuery={searchQuery}
              searchResults={searchResults}
              importTemplates={importTemplates}
              selectedTemplateKey={selectedTemplateKey}
              importPayloadText={importPayloadText}
              replaceSections={replaceSections}
              generationLoadingKind={dispatchingEntityKind}
              generationTask={entityTaskState}
              generationTaskEvents={entityTaskEvents}
              acceptingCandidateIndex={acceptingCandidateIndex}
              storyBibleVersions={storyBibleVersions}
              storyBiblePendingChanges={storyBiblePendingChanges}
              loadingGovernance={loadingStoryBibleGovernance}
              governanceActionKey={storyBibleGovernanceActionKey}
              onTabChange={handleKnowledgeTabChange}
              onFieldChange={(field, value) =>
                setFormState((current) => ({
                  ...current,
                  [field]: value,
                }))
              }
              onSearchQueryChange={setSearchQuery}
              onImportTemplateChange={handleImportTemplateChange}
              onImportPayloadChange={setImportPayloadText}
              onToggleReplaceSection={handleToggleReplaceSection}
              onGenerateSuggestion={(kind) => void handleGenerateSuggestion(kind)}
              onAcceptSuggestion={(candidateIndex) => void handleAcceptSuggestion(candidateIndex)}
              onSearch={() => void handleSearch()}
              onSubmit={() => void handleKnowledgeSave()}
              onSubmitImport={() => void handleSubmitImport()}
              onStartEdit={handleStartEdit}
              onDelete={(tab, id) => void handleDeleteKnowledge(tab, id)}
              onJumpToRelatedChapter={handleJumpToRelatedChapter}
              onLocateSearchResult={handleLocateSearchResult}
              onCancelEdit={handleCancelEdit}
              onApprovePendingChange={(changeId) =>
                void handleApproveStoryBiblePendingChange(changeId)
              }
              onRejectPendingChange={(changeId) =>
                void handleRejectStoryBiblePendingChange(changeId)
              }
              onRollbackVersion={(versionId, versionNumber) =>
                void handleRollbackStoryBibleVersion(versionId, versionNumber)
              }
            />
          </section>
        ) : null}

      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-black/10 bg-white/92 shadow-[0_-12px_40px_rgba(16,20,23,0.08)] backdrop-blur md:hidden">
        <div className="mx-auto max-w-7xl px-4 pb-[calc(env(safe-area-inset-bottom)+12px)] pt-3">
          <button
            className="w-full rounded-2xl bg-copper px-4 py-3 text-sm font-semibold text-white"
            onClick={handlePrimaryStageAction}
            type="button"
          >
            {primaryStageActionLabelMap[recommendedStageCard.key]}
          </button>

          <div className="mt-3 grid grid-cols-4 gap-2">
            {stageCards.map((card) => {
              const isActive = activeStageValue === card.key;
              return (
                <button
                  key={`mobile-dock-${card.key}`}
                  className={`rounded-2xl border px-2 py-2 text-center transition ${
                    isActive
                      ? "border-copper/30 bg-[#fbf3e8] text-copper"
                      : "border-black/10 bg-white text-black/62"
                  }`}
                  onClick={() => openStage(card.key)}
                  type="button"
                >
                  <p className="text-xs font-semibold">{card.title}</p>
                  <p className="mt-1 text-[10px] leading-4 opacity-80">{card.status}</p>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </main>
  );
}
