"use client";

import { useCallback, useMemo, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import type {
  FinalOptimizeResponse,
  StoryBulkImportResponse,
  StoryChapterSummary,
  StoryEngineWorkspace,
  StorySearchResult,
  StoryKnowledgeMutationResponse,
  StoryKnowledgeSuggestionResolveResponse,
  StoryKnowledgeSuggestion,
  StoryBulkImportRequest,
  ProjectEntityGenerationDispatch,
  TaskState,
  TaskEvent,
  StoryGeneratedCandidateAcceptResponse,
} from "@/types/api";

type KnowledgeTabKey = "characters" | "foreshadows" | "items" | "world_rules" | "timeline_events" | "locations" | "factions" | "plot_threads" | "outlines" | "chapter_summaries";
type KnowledgeSuggestionKind = "characters" | "items" | "locations" | "factions" | "plot_threads";

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

type UseStoryRoomKnowledgeOptions = {
  projectId: string;
  workspace: StoryEngineWorkspace | null;
  storyBibleBranchId: string | null;
  onSuccess: (message: string) => void;
  onError: (error: string) => void;
  onWorkspaceRefresh: () => Promise<void>;
  onStoryBibleGovernanceRefresh: () => Promise<void>;
};

type UseStoryRoomKnowledgeReturn = {
  activeTab: KnowledgeTabKey;
  editingId: string | null;
  formState: Record<string, string>;
  savingKnowledge: boolean;
  importingKnowledge: boolean;
  searchQuery: string;
  searchResults: StorySearchResult[];
  entityTaskState: TaskState | null;
  entityTaskEvents: TaskEvent[];
  dispatchingEntityKind: KnowledgeSuggestionKind | null;
  acceptingCandidateIndex: number | null;
  resolvingSuggestionId: string | null;
  setActiveTab: (tab: KnowledgeTabKey) => void;
  setEditingId: (id: string | null) => void;
  setFormState: (state: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => void;
  setSearchQuery: (query: string) => void;
  handleStartEdit: (tab: KnowledgeTabKey, item: Record<string, unknown>) => void;
  handleCancelEdit: () => void;
  handleKnowledgeSave: () => Promise<void>;
  handleDeleteKnowledge: (tab: KnowledgeTabKey, entityId: string) => Promise<void>;
  handleSearch: () => Promise<void>;
  handleLocateSearchResult: (result: StorySearchResult) => void;
  handleGenerateSuggestion: (kind: KnowledgeSuggestionKind) => Promise<void>;
  handleAcceptSuggestion: (candidateIndex: number) => Promise<void>;
  handleResolveKnowledgeSuggestion: (suggestion: StoryKnowledgeSuggestion, action: "apply" | "ignore") => Promise<void>;
  handleImportTemplateChange: (key: string) => void;
  handleSubmitImport: (payload: StoryBulkImportRequest) => Promise<void>;
};

function createClientUuid(): string {
  return crypto.randomUUID();
}

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

function resolveKnowledgeEntityId(tab: KnowledgeTabKey, item: Record<string, unknown>): string {
  const storyBibleTabs: KnowledgeTabKey[] = ["locations", "factions", "plot_threads"];
  if (storyBibleTabs.includes(tab)) {
    const identityFields = ["id", "key", "name", "title", "content"] as const;
    for (const field of identityFields) {
      const value = item[field];
      if (typeof value === "string" && value.trim().length > 0) {
        return `${field}:${value.trim()}`;
      }
    }
    return "";
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

function buildKnowledgePayload(
  tab: KnowledgeTabKey,
  formState: Record<string, string>,
  editingId: string | null,
) {
  const storyBibleTabs: KnowledgeTabKey[] = ["locations", "factions", "plot_threads"];
  if (storyBibleTabs.includes(tab)) {
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
      kb_update_suggestions: current.chapter_summary.kb_update_suggestions.map((item: StoryKnowledgeSuggestion) => {
        const suggestionId = String(item.suggestion_id ?? "");
        return suggestionId === resolvedSuggestion.suggestion_id ? resolvedSuggestion : item;
      }),
    },
    kb_update_list: current.kb_update_list.map((item: StoryKnowledgeSuggestion) =>
      item.suggestion_id === resolvedSuggestion.suggestion_id ? resolvedSuggestion : item,
    ),
  };
}

export function useStoryRoomKnowledge({
  projectId,
  workspace,
  storyBibleBranchId,
  onSuccess,
  onError,
  onWorkspaceRefresh,
  onStoryBibleGovernanceRefresh,
}: UseStoryRoomKnowledgeOptions): UseStoryRoomKnowledgeReturn {
  const [activeTab, setActiveTab] = useState<KnowledgeTabKey>("characters");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formState, setFormState] = useState<Record<string, string>>({});
  const [savingKnowledge, setSavingKnowledge] = useState(false);
  const [importingKnowledge, setImportingKnowledge] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StorySearchResult[]>([]);
  const [entityTaskState, setEntityTaskState] = useState<TaskState | null>(null);
  const [entityTaskEvents, setEntityTaskEvents] = useState<TaskEvent[]>([]);
  const [dispatchingEntityKind, setDispatchingEntityKind] = useState<KnowledgeSuggestionKind | null>(null);
  const [acceptingCandidateIndex, setAcceptingCandidateIndex] = useState<number | null>(null);
  const [resolvingSuggestionId, setResolvingSuggestionId] = useState<string | null>(null);

  const handleStartEdit = useCallback((tab: KnowledgeTabKey, item: Record<string, unknown>) => {
    setActiveTab(tab);
    setEditingId(resolveKnowledgeEntityId(tab, item));
    setFormState(buildEditForm(tab, item));
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setFormState({});
  }, []);

  const handleKnowledgeSave = useCallback(async () => {
    setSavingKnowledge(true);
    onError("");
    onSuccess("");
    try {
      const storyBibleTabs: KnowledgeTabKey[] = ["locations", "factions", "plot_threads"];
      const payload = buildKnowledgePayload(activeTab, formState, editingId);
      const branchId = storyBibleTabs.includes(activeTab) ? storyBibleBranchId : null;

      if (storyBibleTabs.includes(activeTab) && !branchId) {
        throw new Error("当前项目还没有默认主线，暂时不能保存这类设定。");
      }

      const result = await apiFetchWithAuth<StoryKnowledgeMutationResponse>(
        `/api/v1/projects/${projectId}/story-engine/knowledge/${activeTab}`,
        {
          method: "POST",
          body: JSON.stringify({
            entity_id: editingId,
            branch_id: branchId,
            previous_entity_key: storyBibleTabs.includes(activeTab) ? editingId : null,
            item: payload,
          }),
        },
      );

      setEditingId(null);
      setFormState({});
      onSuccess(result.message);
      await onWorkspaceRefresh();
      await onStoryBibleGovernanceRefresh();
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setSavingKnowledge(false);
    }
  }, [activeTab, editingId, formState, onError, onSuccess, projectId, storyBibleBranchId, onWorkspaceRefresh, onStoryBibleGovernanceRefresh]);

  const handleDeleteKnowledge = useCallback(async (tab: KnowledgeTabKey, entityId: string) => {
    onError("");
    onSuccess("");
    try {
      const storyBibleTabs: KnowledgeTabKey[] = ["locations", "factions", "plot_threads"];
      const branchId = storyBibleTabs.includes(tab) ? storyBibleBranchId : null;
      if (storyBibleTabs.includes(tab) && !branchId) {
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
      onSuccess(result.message);
      await onWorkspaceRefresh();
      await onStoryBibleGovernanceRefresh();
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    }
  }, [onError, onSuccess, projectId, storyBibleBranchId, onWorkspaceRefresh, onStoryBibleGovernanceRefresh]);

  const handleSearch = useCallback(async () => {
    const normalizedQuery = searchQuery.trim();
    if (!normalizedQuery) {
      setSearchResults([]);
      return;
    }
    try {
      const data = await apiFetchWithAuth<StorySearchResult[]>(
        `/api/v1/projects/${projectId}/story-engine/search?query=${encodeURIComponent(normalizedQuery)}`,
      );
      setSearchResults(data);
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    }
  }, [onError, projectId, searchQuery]);

  const handleLocateSearchResult = useCallback((result: StorySearchResult) => {
    const entityTypeToTab: Record<string, KnowledgeTabKey | null> = {
      characters: "characters",
      foreshadows: "foreshadows",
      items: "items",
      locations: "locations",
      factions: "factions",
      plot_threads: "plot_threads",
      world_rules: "world_rules",
      timeline_events: "timeline_events",
    };
    const tab = entityTypeToTab[result.entity_type] ?? null;
    if (!tab) {
      onError("这条搜索结果暂时不能直接定位到设定卡片。");
      return;
    }

    setActiveTab(tab);
    onSuccess("已定位到对应设定条目。");
  }, [onError, onSuccess]);

  const handleGenerateSuggestion = useCallback(async (kind: KnowledgeSuggestionKind) => {
    setDispatchingEntityKind(kind);
    onError("");
    onSuccess("");

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
      onSuccess(`已经开始补${ENTITY_GENERATION_SUCCESS_LABELS[kind]}，结果会挂在右侧。`);
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setDispatchingEntityKind(null);
    }
  }, [onError, onSuccess, projectId, workspace]);

  const handleAcceptSuggestion = useCallback(async (candidateIndex: number) => {
    if (!entityTaskState) {
      onError("当前没有可采纳的补全结果。");
      return;
    }

    setAcceptingCandidateIndex(candidateIndex);
    onError("");
    onSuccess("");

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

      await onWorkspaceRefresh();
      if (
        data.accepted_entity_type === "characters" ||
        data.accepted_entity_type === "items" ||
        data.accepted_entity_type === "locations" ||
        data.accepted_entity_type === "factions" ||
        data.accepted_entity_type === "plot_threads"
      ) {
        setActiveTab(data.accepted_entity_type as KnowledgeTabKey);
      }
      onSuccess(data.message);
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setAcceptingCandidateIndex(null);
    }
  }, [entityTaskState, onError, onSuccess, projectId, storyBibleBranchId, onWorkspaceRefresh]);

  const handleResolveKnowledgeSuggestion = useCallback(async (
    suggestion: StoryKnowledgeSuggestion,
    action: "apply" | "ignore",
  ) => {
    setResolvingSuggestionId(suggestion.suggestion_id);
    onError("");
    onSuccess("");
    try {
      const response = await apiFetchWithAuth<StoryKnowledgeSuggestionResolveResponse>(
        `/api/v1/projects/${projectId}/story-engine/chapter-summaries/placeholder/kb-updates/${suggestion.suggestion_id}`,
        {
          method: "POST",
          body: JSON.stringify({ action }),
        },
      );
      onSuccess(response.message);
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setResolvingSuggestionId(null);
    }
  }, [onError, onSuccess, projectId]);

  const handleImportTemplateChange = useCallback((_key: string) => {
    // Template change handler - to be implemented with actual template data
  }, []);

  const handleSubmitImport = useCallback(async (_payload: StoryBulkImportRequest) => {
    setImportingKnowledge(true);
    onError("");
    onSuccess("");

    try {
      // Import logic to be implemented
      onSuccess("设定导入完成。");
      await onWorkspaceRefresh();
      await onStoryBibleGovernanceRefresh();
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setImportingKnowledge(false);
    }
  }, [onError, onSuccess, onWorkspaceRefresh, onStoryBibleGovernanceRefresh]);

  return {
    activeTab,
    editingId,
    formState,
    savingKnowledge,
    importingKnowledge,
    searchQuery,
    searchResults,
    entityTaskState,
    entityTaskEvents,
    dispatchingEntityKind,
    acceptingCandidateIndex,
    resolvingSuggestionId,
    setActiveTab,
    setEditingId,
    setFormState,
    setSearchQuery,
    handleStartEdit,
    handleCancelEdit,
    handleKnowledgeSave,
    handleDeleteKnowledge,
    handleSearch,
    handleLocateSearchResult,
    handleGenerateSuggestion,
    handleAcceptSuggestion,
    handleResolveKnowledgeSuggestion,
    handleImportTemplateChange,
    handleSubmitImport,
  };
}