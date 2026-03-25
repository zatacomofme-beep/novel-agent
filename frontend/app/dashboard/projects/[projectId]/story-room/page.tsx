"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FinalPublishPanel } from "@/components/story-engine/final-publish-panel";
import { DraftStudio } from "@/components/story-engine/draft-studio";
import { FinalDiffViewer } from "@/components/story-engine/final-diff-viewer";
import { ChapterReviewPanel } from "@/components/story-engine/chapter-review-panel";
import { StyleControlPanel } from "@/components/story-engine/style-control-panel";
import {
  KnowledgeBaseBoard,
  type KnowledgeSuggestionKind,
  type KnowledgeTabKey,
} from "@/components/story-engine/knowledge-base-board";
import { OutlineWorkbench } from "@/components/story-engine/outline-workbench";
import { apiFetchWithAuth, apiStreamWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
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
  RealtimeGuardResponse,
  RollbackResponse,
  StoryBible,
  StoryBiblePendingChange,
  StoryBiblePendingChangeList,
  StoryBibleVersion,
  StoryBibleVersionList,
  StoryBulkImportResponse,
  StoryEngineWorkspace,
  StoryGeneratedCandidateAcceptResponse,
  StoryKnowledgeSuggestion,
  StoryKnowledgeSuggestionResolveResponse,
  StoryKnowledgeMutationResponse,
  StoryImportTemplate,
  StorySearchResult,
  StoryOutline,
  StyleTemplate,
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

function selectLatestTask(taskData: TaskState[]): TaskState | null {
  return [...taskData].sort((left, right) => {
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  })[0] ?? null;
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

function isChapterInDefaultScope(chapter: Chapter, structure: ProjectStructure | null): boolean {
  if (structure?.default_branch_id && chapter.branch_id !== structure.default_branch_id) {
    return false;
  }
  if (structure?.default_volume_id && chapter.volume_id !== structure.default_volume_id) {
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
  structure: ProjectStructure | null,
  chapterNumber: number,
): string[] {
  return chapters
    .filter(
      (chapter) =>
        chapter.chapter_number < chapterNumber &&
        isChapterInDefaultScope(chapter, structure) &&
        chapter.content.trim().length > 0,
    )
    .sort((left, right) => right.chapter_number - left.chapter_number)
    .slice(0, 2)
    .map((chapter) => chapter.content);
}

export default function StoryRoomPage() {
  const params = useParams<ProjectRouteParams>();
  const projectId = params.projectId;
  const hydratedChapterKeyRef = useRef<string | null>(null);
  const bootstrapHydratedRef = useRef(false);
  const editorTextareaRef = useRef<HTMLTextAreaElement>(null);

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
  const [exportingFormat, setExportingFormat] = useState<"md" | "txt" | null>(null);
  const [finalizingChapter, setFinalizingChapter] = useState(false);
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
  const [dispatchingEntityKind, setDispatchingEntityKind] =
    useState<KnowledgeSuggestionKind | null>(null);
  const [acceptingCandidateIndex, setAcceptingCandidateIndex] = useState<number | null>(null);
  const [activeStage, setActiveStage] = useState<StoryRoomStageKey | null>(null);
  const [pendingStageScroll, setPendingStageScroll] = useState<StoryRoomStageKey | null>(null);

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

  const activeChapter = useMemo(() => {
    const matches = chapters.filter((chapter) => chapter.chapter_number === chapterNumber);
    return matches.find((chapter) => isChapterInDefaultScope(chapter, projectStructure)) ?? matches[0] ?? null;
  }, [chapterNumber, chapters, projectStructure]);

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

  const defaultVolumeTitle = useMemo(() => {
    if (!projectStructure?.default_volume_id) {
      return "默认卷";
    }
    return (
      projectStructure.volumes.find((item) => item.id === projectStructure.default_volume_id)?.title ??
      "默认卷"
    );
  }, [projectStructure]);

  const defaultBranchTitle = useMemo(() => {
    if (!projectStructure?.default_branch_id) {
      return "默认主线";
    }
    return (
      projectStructure.branches.find((item) => item.id === projectStructure.default_branch_id)?.title ??
      "默认主线"
    );
  }, [projectStructure]);

  const savedChapterCount = useMemo(
    () => chapters.filter((chapter) => isChapterInDefaultScope(chapter, projectStructure)).length,
    [chapters, projectStructure],
  );

  const recentChapterTexts = useMemo(() => {
    const chapterContents = buildRecentChapterTexts(chapters, projectStructure, chapterNumber);
    if (chapterContents.length > 0) {
      return chapterContents;
    }
    return (workspace?.chapter_summaries ?? [])
      .filter((item) => item.chapter_number < chapterNumber)
      .sort((left, right) => right.chapter_number - left.chapter_number)
      .slice(0, 2)
      .map((item) => item.content);
  }, [chapterNumber, chapters, projectStructure, workspace?.chapter_summaries]);

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
    } satisfies FinalOptimizeResponse;
  }, [draftText, finalResult, persistedChapterSummary]);

  const canApplyOptimizedDraft = useMemo(() => {
    if (!finalResult) {
      return false;
    }
    return finalResult.final_draft.trim().length > 0 && finalResult.final_draft !== draftText;
  }, [draftText, finalResult]);

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
  const stageCards: Array<{
    key: StoryRoomStageKey;
    kicker: string;
    title: string;
    description: string;
    status: string;
  }> = [
    {
      key: "outline",
      kicker: "第一步",
      title: "定故事",
      description: "把故事核心设定压成三级大纲和锁死主线。",
      status: hasOutlineBlueprint ? `${level3OutlineList.length} 条章纲` : "待先生成",
    },
    {
      key: "draft",
      kicker: "第二步",
      title: "写正文",
      description: "先对准当前章节细纲，再一键开始出正文。",
      status: draftText.trim().length > 0 ? `第 ${chapterNumber} 章进行中` : "待开始",
    },
    {
      key: "final",
      kicker: "第三步",
      title: "看优化",
      description: "把初稿收口成终稿，对比修改点和发布状态。",
      status: hasOptimizationResult ? "已有终稿包" : "待生成",
    },
    {
      key: "knowledge",
      kicker: "第四步",
      title: "管设定",
      description: "人物、伏笔、物品和时间线都在这里沉淀和修订。",
      status:
        storyBiblePendingChanges.length > 0
          ? `待确认 ${storyBiblePendingChanges.length} 条`
          : `${knowledgeItemCount} 条设定`,
    },
  ];
  const recommendedStageCard =
    stageCards.find((item) => item.key === recommendedStage) ?? stageCards[0];
  const recommendedStageActionLabelMap: Record<StoryRoomStageKey, string> = {
    outline: "先生成大纲",
    draft: "开始写正文",
    final: "去看优化稿",
    knowledge: "处理设定",
  };
  const recommendedStageSummaryMap: Record<StoryRoomStageKey, string> = {
    outline: "先把故事核心、题材气质和体量压成可写的三级大纲。",
    draft: currentOutline
      ? `第 ${chapterNumber} 章已经挂到三级大纲上，可以直接开始出正文。`
      : "先从三级大纲里选一章，再开始出正文。",
    final: "正文起出来后，就来这里看优化稿和修改依据。",
    knowledge:
      storyBiblePendingChanges.length > 0
        ? `这轮有 ${storyBiblePendingChanges.length} 条设定待确认。`
        : "写完后回这里收设定，平时不用一直盯着。",
  };

  const scopeLabel = `${defaultBranchTitle} · ${defaultVolumeTitle}`;
  const storyBibleBranchId = storyBible?.scope.branch_id ?? projectStructure?.default_branch_id ?? null;

  const openStage = useCallback((stage: StoryRoomStageKey, options?: { scroll?: boolean }) => {
    setActiveStage(stage);
    if (options?.scroll === false) {
      return;
    }
    setPendingStageScroll(stage);
  }, []);

  function handleSelectOutlineId(outlineId: string) {
    const outline = level3OutlineList.find((item) => item.outline_id === outlineId);
    if (!outline) {
      return;
    }
    setActiveStage("draft");
    setChapterNumber(outline.node_order);
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

  const loadProjectEntityTaskState = useCallback(async () => {
    try {
      const taskData = await apiFetchWithAuth<TaskState[]>(
        `/api/v1/projects/${projectId}/tasks?task_type_prefix=entity_generation&limit=8`,
      );
      setEntityTaskState(selectLatestTask(taskData));
    } catch (requestError) {
      setEntityTaskState(null);
      setError(buildUserFriendlyError(requestError));
    }
  }, [projectId]);

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

  const loadWorkspace = useCallback(async (showSpinner = true) => {
    if (showSpinner) {
      setLoading(true);
    }
    setError(null);
    try {
      const [workspaceData, templateData] = await Promise.all([
        apiFetchWithAuth<StoryEngineWorkspace>(
          `/api/v1/projects/${projectId}/story-engine/workspace`,
        ),
        apiFetchWithAuth<StoryImportTemplate[]>(
          `/api/v1/projects/${projectId}/story-engine/import-templates`,
        ),
        refreshChapterChainState(),
      ]);
      setWorkspace(workspaceData);
      setStoryBible(workspaceData.story_bible ?? null);
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

  const loadProjectBootstrap = useCallback(async (showError = false) => {
    try {
      const data = await apiFetchWithAuth<ProjectBootstrapState>(
        `/api/v1/projects/${projectId}/bootstrap`,
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
    void loadWorkspace();
  }, [loadWorkspace, projectId]);

  useEffect(() => {
    setActiveStage((current) => current ?? recommendedStage);
  }, [recommendedStage]);

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
      `new:${projectStructure.default_branch_id ?? "default"}:${projectStructure.default_volume_id ?? "default"}:${chapterNumber}`;
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
    }
    hydratedChapterKeyRef.current = chapterKey;
    setDraftDirty(false);
  }, [
    activeChapter?.content,
    activeChapter?.current_version_number,
    activeChapter?.id,
    activeChapter?.title,
    chapterNumber,
    draftDirty,
    projectStructure,
  ]);

  useEffect(() => {
    if (!activeChapter?.id) {
      setExportingFormat(null);
      setFinalizingChapter(false);
      return;
    }
    setExportingFormat(null);
    setFinalizingChapter(false);
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
      const data = await apiFetchWithAuth<ProjectBootstrapState>(
        `/api/v1/projects/${projectId}/bootstrap`,
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
      await loadWorkspace(false);
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
      setActiveStage("outline");
      setPendingStageScroll("outline");
      setSuccess("大纲已经压成可写结构，一级大纲已锁死。");
      await Promise.all([loadWorkspace(), loadProjectBootstrap()]);
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
    chapterNumber,
    chapterTitle,
    currentOutline?.content,
    currentOutline?.outline_id,
    draftText,
    projectId,
    recentChapterTexts,
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
            chapter_number: chapterNumber,
            chapter_title: chapterTitle || null,
            draft_text: draftText,
            style_sample: styleSample || null,
          }),
        },
      );
      setFinalResult(data);
      setActiveStage("final");
      setPendingStageScroll("final");
      setSuccess(
        data.ready_for_publish
          ? data.quality_summary ?? successMessage
          : data.quality_summary ?? "这轮深度收口还没完全结束，右下方先看问题和优化稿。",
      );
      await loadWorkspace();
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
      await loadWorkspace(false);
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
        setSuccess(`第 ${chapterNumber} 章已保存，版本和发布状态都会按这版继续跟进。`);
      } else {
        const createdChapter = await apiFetchWithAuth<Chapter>(
          `/api/v1/projects/${projectId}/chapters`,
          {
            method: "POST",
            body: JSON.stringify({
              chapter_number: chapterNumber,
              volume_id: projectStructure.default_volume_id,
              branch_id: projectStructure.default_branch_id,
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

  async function handleSaveAsFinal() {
    if (!activeChapter) {
      setError("请先把这一章保存成正式章节，再尝试放行。");
      return;
    }
    if (draftDirty) {
      setError("当前还有未保存改动，请先保存正文，再尝试放行。");
      return;
    }

    setFinalizingChapter(true);
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

      setChapters((current) =>
        sortChapters([
          ...current.filter((chapter) => chapter.id !== updatedChapter.id),
          updatedChapter,
        ]),
      );
      await refreshChapterChainState();
      setSuccess(
        updatedChapter.status === "final"
          ? "这章已经标记为终稿状态，可以直接导出交稿版。"
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
      setFinalizingChapter(false);
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
        loadWorkspace(false),
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
        loadWorkspace(false),
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
        ? storyBible?.scope.branch_id ?? projectStructure?.default_branch_id ?? null
        : null;

      if (isStoryBibleKnowledgeTab(activeTab) && !branchId) {
        throw new Error("当前项目还没有默认主线，暂时不能保存这类主设定。");
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
      await loadWorkspace();
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
        ? storyBible?.scope.branch_id ?? projectStructure?.default_branch_id ?? null
        : null;
      if (isStoryBibleKnowledgeTab(tab) && !branchId) {
        throw new Error("当前项目还没有默认主线，暂时不能删除这类主设定。");
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
      await loadWorkspace();
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const data = await apiFetchWithAuth<StorySearchResult[]>(
        `/api/v1/projects/${projectId}/story-engine/search?query=${encodeURIComponent(searchQuery)}`,
      );
      setSearchResults(data);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    }
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
            template_key: selectedTemplateKey || null,
            apply_template_model_routing: false,
            replace_existing_sections: replaceSections,
            payload: parsedPayload,
          }),
        },
      );
      setStressResult(null);
      setSuccess(buildImportSummary(data));
      await loadWorkspace();
      await loadStoryBibleGovernanceState(storyBibleBranchId, false);
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
            branch_id: storyBible?.scope.branch_id ?? projectStructure?.default_branch_id ?? null,
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

      await loadWorkspace();
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
    <main className="min-h-screen px-4 py-8 md:px-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-[42px] border border-black/10 bg-white/78 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)] md:p-8">
          <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-copper">写作现场</p>
              <h1 className="mt-2 text-3xl font-semibold">{workspace?.project.title}</h1>
              <p className="mt-3 text-sm text-black/58">
                只走一条主路径：定故事，写正文，看优化，收设定。
              </p>
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

              <div className="mt-6 rounded-[28px] border border-copper/20 bg-[#fff7ef] p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-copper">当前建议先做</p>
                <h2 className="mt-2 text-xl font-semibold">{recommendedStageCard.title}</h2>
                <p className="mt-3 text-sm leading-7 text-black/62">
                  {recommendedStageSummaryMap[recommendedStageCard.key]}
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
                    onClick={() => openStage(recommendedStageCard.key)}
                    type="button"
                  >
                    {recommendedStageActionLabelMap[recommendedStageCard.key]}
                  </button>
                  <Link
                    className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                    href="/dashboard"
                  >
                    返回项目总览
                  </Link>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
                <p className="text-sm font-semibold">四步写作路径</p>
                <div className="mt-4 space-y-3">
                  {stageCards.map((card, index) => {
                    const isActive = activeStageValue === card.key;
                    const isRecommended = recommendedStage === card.key;
                    return (
                      <button
                        key={card.key}
                        className={`flex w-full items-center justify-between rounded-[22px] border px-4 py-3 text-left transition ${
                          isActive
                            ? "border-copper/30 bg-white shadow-[0_14px_30px_rgba(176,112,53,0.1)]"
                            : "border-black/10 bg-white/70 hover:bg-white"
                        }`}
                        onClick={() => openStage(card.key)}
                        type="button"
                      >
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-black/10 bg-[#fbfaf5] text-xs font-semibold text-black/62">
                            {index + 1}
                          </span>
                          <div>
                            <p className="text-sm font-semibold">{card.title}</p>
                            <p className="text-xs text-black/52">{card.status}</p>
                          </div>
                        </div>
                        {isRecommended ? (
                          <span className="rounded-full border border-copper/20 bg-[#fff7ef] px-3 py-1 text-xs text-copper">
                            当前
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              </section>

              <div className="grid gap-4 sm:grid-cols-2">
                <article className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
                  <p className="text-sm text-black/55">主线范围</p>
                  <p className="mt-3 text-lg font-semibold">{scopeLabel}</p>
                </article>
                <article className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
                  <p className="text-sm text-black/55">已存章节</p>
                  <p className="mt-3 text-lg font-semibold">{savedChapterCount} 章</p>
                </article>
                <article className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
                  <p className="text-sm text-black/55">体量目标</p>
                  <p className="mt-3 text-lg font-semibold">
                    {effectiveTargetChapterCount} 章 / {targetTotalWords.toLocaleString()} 字
                  </p>
                </article>
                <article className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
                  <p className="text-sm text-black/55">设定待确认</p>
                  <p className="mt-3 text-lg font-semibold">{storyBiblePendingChanges.length} 条</p>
                </article>
              </div>
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

        {activeStageValue === "outline" ? (
          <section id="story-stage-outline" className="scroll-mt-6 space-y-4">
            <div className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.18em] text-copper">第一步</p>
              <h2 className="mt-2 text-2xl font-semibold">先准备大纲输入</h2>
              <p className="mt-3 text-sm text-black/58">输入想法，或者上传已有大纲。</p>
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
              onOpenDraftStep={() => openStage("draft")}
            />
          </section>
        ) : null}

        {activeStageValue === "draft" ? (
          <section id="story-stage-draft" className="scroll-mt-6 space-y-4">
            <div className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.18em] text-copper">第二步</p>
              <h2 className="mt-2 text-2xl font-semibold">先选章节，再开始出正文</h2>
              <p className="mt-3 text-sm text-black/58">正文只跟三级大纲走。</p>
            </div>

            <DraftStudio
              chapterNumber={chapterNumber}
              chapterTitle={chapterTitle}
              draftText={draftText}
              outlines={outlineList}
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
              editorTextareaRef={editorTextareaRef}
              onChapterNumberChange={(value) => setChapterNumber(value)}
              onChapterTitleChange={(value) => {
                setChapterTitle(value);
                setDraftDirty(true);
              }}
              onDraftTextChange={(value) => {
                setDraftText(value);
                setDraftDirty(true);
              }}
              onSelectOutlineId={handleSelectOutlineId}
              onSaveDraft={() => void handleSaveDraft()}
              onRunStreamGenerate={() => void handleRunStreamGenerate()}
              onContinueWithRepair={(option) => void handleContinueWithRepair(option)}
              onContinueAfterManualFix={() => void handleContinueAfterManualFix()}
              onRunGuardCheck={() => void triggerGuardCheck(true)}
              onRunOptimize={() => void handleRunOptimize()}
              onAutoRemember={() => void handleRunOptimize("本章总结和设定更新建议已经自动记下来了。")}
              onOpenOutlineStep={() => openStage("outline")}
            />

            <StyleControlPanel
              chapterSample={styleSample}
              preferenceProfile={preferenceProfile}
              styleTemplates={styleTemplates}
              loading={loadingStyleControl}
              actionKey={styleActionKey}
              onChapterSampleChange={setStyleSample}
              onApplyTemplate={(templateKey) => void handleApplyStyleTemplate(templateKey)}
              onClearTemplate={() => void handleClearStyleTemplate()}
              onSavePreference={(payload) => void handleSaveStylePreference(payload)}
            />
          </section>
        ) : null}

        {activeStageValue === "final" ? (
          <section id="story-stage-final" className="scroll-mt-6 space-y-4">
            <div className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.18em] text-copper">第三步</p>
              <h2 className="mt-2 text-2xl font-semibold">看终稿对比，再决定是否放行</h2>
              <p className="mt-3 text-sm text-black/58">这里只看结果，不再回头起稿。</p>
              {!visibleFinalResult ? (
                <div className="mt-4 flex flex-wrap items-center gap-3 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm text-black/62">
                  这章还没有跑出优化结果。
                  <button
                    className="rounded-full bg-copper px-4 py-2 text-sm font-semibold text-white"
                    onClick={() => openStage("draft")}
                    type="button"
                  >
                    回正文区继续
                  </button>
                </div>
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
              exportingFormat={exportingFormat}
              finalizingChapter={finalizingChapter}
              canApplyOptimizedDraft={canApplyOptimizedDraft}
              onOpenDraftStep={() => openStage("draft")}
              onApplyOptimizedDraft={() => handleApplyOptimizedDraft()}
              onSaveAsFinal={() => void handleSaveAsFinal()}
              onExport={(format) => void handleExportChapter(format)}
            />
          </section>
        ) : null}

        {activeStageValue === "knowledge" ? (
          <section id="story-stage-knowledge" className="scroll-mt-6 space-y-4">
            <div className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.18em] text-copper">第四步</p>
              <h2 className="mt-2 text-2xl font-semibold">最后确认设定圣经</h2>
              <p className="mt-3 text-sm text-black/58">默认先写，最后回来收设定。</p>
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

        <details className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <summary className="cursor-pointer list-none text-lg font-semibold">
            更多高级工具：版本、批注、回退与章节复核
          </summary>
          <p className="mt-3 text-sm leading-7 text-black/60">
            这部分默认收起来，避免打断主路径。只有当你要做版本对比、精确批注或回退章节时，再展开使用。
          </p>
          <div className="mt-5">
            <ChapterReviewPanel
              activeChapter={activeChapter}
              draftText={draftText}
              draftDirty={draftDirty}
              reviewWorkspace={reviewWorkspace}
              chapterVersions={chapterVersions}
              loading={loadingChapterReview}
              submittingActionKey={reviewSubmittingActionKey}
              editorTextareaRef={editorTextareaRef}
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
      </div>
    </main>
  );
}
