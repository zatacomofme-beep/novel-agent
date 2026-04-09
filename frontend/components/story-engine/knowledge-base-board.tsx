"use client";

import { useEffect, useRef } from "react";

import { formatDateTime } from "@/components/editor/formatters";
import type {
  LocationItem,
  PlotThreadItem,
  StoryBible,
  StoryBiblePendingChange,
  StoryBibleVersion,
  StoryCharacter,
  StoryEngineWorkspace,
  StoryBibleFactionEntry,
  StoryForeshadow,
  StoryImportTemplate,
  StoryItem,
  StorySearchResult,
  StoryTimelineMapEvent,
  StoryWorldRule,
  TaskEvent,
  TaskState,
} from "@/types/api";

export type KnowledgeTabKey =
  | "characters"
  | "foreshadows"
  | "items"
  | "locations"
  | "factions"
  | "plot_threads"
  | "world_rules"
  | "timeline_events";

export type KnowledgeSuggestionKind =
  | "characters"
  | "items"
  | "locations"
  | "factions"
  | "plot_threads";

type KnowledgeBaseBoardProps = {
  workspace: StoryEngineWorkspace | null;
  storyBible: StoryBible | null;
  activeTab: KnowledgeTabKey;
  highlightedItemId: string | null;
  editingId: string | null;
  formState: Record<string, string>;
  saving: boolean;
  importing: boolean;
  searchQuery: string;
  searchResults: StorySearchResult[];
  importTemplates: StoryImportTemplate[];
  selectedTemplateKey: string;
  importPayloadText: string;
  replaceSections: string[];
  generationLoadingKind: KnowledgeSuggestionKind | null;
  generationTask: TaskState | null;
  generationTaskEvents: TaskEvent[];
  acceptingCandidateIndex: number | null;
  storyBibleVersions: StoryBibleVersion[];
  storyBiblePendingChanges: StoryBiblePendingChange[];
  loadingGovernance: boolean;
  governanceActionKey: string | null;
  onTabChange: (tab: KnowledgeTabKey) => void;
  onFieldChange: (field: string, value: string) => void;
  onSearchQueryChange: (value: string) => void;
  onImportTemplateChange: (value: string) => void;
  onImportPayloadChange: (value: string) => void;
  onToggleReplaceSection: (section: string) => void;
  onGenerateSuggestion: (kind: KnowledgeSuggestionKind) => void;
  onAcceptSuggestion: (candidateIndex: number) => void;
  onSearch: () => void;
  onSubmit: () => void;
  onSubmitImport: () => void;
  onStartEdit: (tab: KnowledgeTabKey, item: Record<string, unknown>) => void;
  onDelete: (tab: KnowledgeTabKey, id: string) => void;
  onJumpToRelatedChapter: (tab: KnowledgeTabKey, item: Record<string, unknown>) => void;
  onLocateSearchResult: (result: StorySearchResult) => void;
  onCancelEdit: () => void;
  onApprovePendingChange: (changeId: string) => void;
  onRejectPendingChange: (changeId: string) => void;
  onRollbackVersion: (versionId: string, versionNumber: number) => void;
};

const TAB_LABELS: Record<KnowledgeTabKey, string> = {
  characters: "人物",
  foreshadows: "伏笔",
  items: "物品",
  locations: "地点",
  factions: "势力",
  plot_threads: "剧情线",
  world_rules: "规则",
  timeline_events: "时间线",
};

const IMPORT_SECTION_OPTIONS = [
  { key: "characters", label: "人物" },
  { key: "foreshadows", label: "伏笔" },
  { key: "items", label: "物品" },
  { key: "world_rules", label: "规则" },
  { key: "timeline_events", label: "时间线" },
  { key: "outlines", label: "大纲" },
  { key: "chapter_summaries", label: "章节总结" },
];

const GENERATION_ACTIONS: Array<{
  key: KnowledgeSuggestionKind;
  label: string;
}> = [
  { key: "characters", label: "补几个人物" },
  { key: "items", label: "补几件物品" },
  { key: "locations", label: "补几个地点" },
  { key: "factions", label: "补一个势力" },
  { key: "plot_threads", label: "补几条剧情线" },
];

const GENERATION_TASK_LABELS: Record<string, string> = {
  "entity_generation.characters": "补几个人物",
  "entity_generation.supporting": "补几个配角",
  "entity_generation.items": "补几件物品",
  "entity_generation.locations": "补几个地点",
  "entity_generation.factions": "补一个势力",
  "entity_generation.plot_threads": "补几条剧情线",
};

const GENERATION_STATUS_LABELS: Record<TaskState["status"], string> = {
  queued: "排队中",
  running: "整理中",
  succeeded: "已备好",
  failed: "这轮没跑通",
};

const STORY_BIBLE_SECTION_LABELS: Record<string, string> = {
  characters: "人物",
  world_settings: "世界设定",
  items: "物品",
  factions: "势力",
  locations: "地点",
  plot_threads: "剧情线",
  foreshadowing: "伏笔",
  timeline_events: "时间线",
};

const STORY_BIBLE_CHANGE_TYPE_LABELS: Record<string, string> = {
  added: "新增",
  updated: "修改",
  removed: "删除",
};

const STORY_BIBLE_CHANGE_SOURCE_LABELS: Record<string, string> = {
  user: "手动改动",
  ai_proposed: "自动建议",
  auto_trigger: "自动触发",
};

function FieldLabel({ label }: { label: string }) {
  return <span className="text-sm text-black/60">{label}</span>;
}

function QuickField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label className="block">
      <FieldLabel label={label} />
      {multiline ? (
        <textarea
          className="mt-2 min-h-[104px] w-full rounded-[20px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <input
          className="mt-2 w-full rounded-[20px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function renderStoryBibleSummaryCard(
  cardKey: string,
  title: string,
  detail: string,
  meta: string[],
) {
  return (
    <article
      key={cardKey}
      className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4"
    >
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-2 text-sm leading-7 text-black/58">{detail}</p>
      {meta.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/52">
          {meta.map((item) => (
            <span
              key={item}
              className="rounded-full border border-black/10 bg-white px-3 py-1"
            >
              {item}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function truncateText(value: string | null | undefined, limit = 80): string {
  const text = (value ?? "").trim().replace(/\s+/g, " ");
  if (!text) {
    return "";
  }
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
}

function extractStoryBibleEntityLabel(
  value: Record<string, unknown> | null | undefined,
): string | null {
  if (!value) {
    return null;
  }
  for (const field of ["name", "title", "rule_name", "content", "key"] as const) {
    const nextValue = value[field];
    if (typeof nextValue === "string" && nextValue.trim().length > 0) {
      return nextValue.trim();
    }
  }
  return null;
}

function formatStoryBibleSectionLabel(section: string): string {
  return STORY_BIBLE_SECTION_LABELS[section] ?? section;
}

function formatStoryBibleChangeType(type: string): string {
  return STORY_BIBLE_CHANGE_TYPE_LABELS[type] ?? type;
}

function formatStoryBibleChangeSource(source: string): string {
  return STORY_BIBLE_CHANGE_SOURCE_LABELS[source] ?? source;
}

function summarizeStoryBibleChange(
  item: Pick<
    StoryBibleVersion | StoryBiblePendingChange,
    "changed_entity_key" | "changed_section" | "new_value" | "old_value"
  >,
): string {
  const label =
    extractStoryBibleEntityLabel(item.new_value) ??
    extractStoryBibleEntityLabel(item.old_value) ??
    item.changed_entity_key ??
    "未命名条目";
  return `${formatStoryBibleSectionLabel(item.changed_section)} · ${truncateText(label, 32)}`;
}

function formatGenerationTaskLabel(task: TaskState | null): string {
  if (!task) {
    return "灵感补全";
  }
  return GENERATION_TASK_LABELS[task.task_type] ?? "灵感补全";
}

function extractSuggestionCards(task: TaskState | null): Array<{
  index: number;
  title: string;
  detail: string;
  canAccept: boolean;
}> {
  const result = task?.result;
  if (!result) {
    return [];
  }

  const generationType = typeof result.generation_type === "string" ? result.generation_type : null;
  if (!generationType) {
    return [];
  }
  const canAccept =
    generationType === "characters" ||
    generationType === "supporting" ||
    generationType === "items" ||
    generationType === "locations" ||
    generationType === "factions" ||
    generationType === "plot_threads";

  const resultKey = generationType === "supporting" ? "characters" : generationType;
  const rawCandidates = result[resultKey];
  if (!Array.isArray(rawCandidates)) {
    return [];
  }

  return rawCandidates.slice(0, 4).flatMap((candidate, index) => {
    if (!candidate || typeof candidate !== "object") {
      return [];
    }
    const record = candidate as Record<string, unknown>;
    const titleValue = record.name ?? record.title;
    if (typeof titleValue !== "string" || titleValue.trim().length === 0) {
      return [];
    }

    const detail = [
      record.personality,
      record.description,
      record.goals,
      record.motivation,
      record.resolution,
    ].find((value) => typeof value === "string" && value.trim().length > 0);

    return [
      {
        index,
        title: titleValue.trim(),
        detail:
          typeof detail === "string" && detail.trim().length > 0
            ? detail.trim()
            : "先拿去当灵感草稿，不满意就继续补一轮。",
        canAccept,
      },
    ];
  });
}

function formatEntityGenerationEventLabel(event: TaskEvent): string {
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
  return labels[event.event_type] ?? event.event_type;
}

function summarizeEntityGenerationEventPayload(payload: Record<string, unknown> | null): string[] {
  if (!payload) {
    return [];
  }

  const summary: string[] = [];

  if (typeof payload.requested_count === "number") {
    summary.push(`目标 ${payload.requested_count} 条`);
  }
  if (typeof payload.candidate_count === "number") {
    summary.push(`整理出 ${payload.candidate_count} 条`);
  } else if (typeof payload.returned_count === "number") {
    summary.push(`整理出 ${payload.returned_count} 条`);
  }
  if (typeof payload.response_source === "string") {
    if (payload.response_source === "local_fallback") {
      summary.push("已启用备用方案");
    } else if (payload.response_source === "model_response") {
      summary.push("已走主方案");
    }
  }
  if (payload.failover_triggered === true) {
    summary.push("已自动切换备用模型");
  }
  if (Array.isArray(payload.entity_preview) && payload.entity_preview.length > 0) {
    const preview = payload.entity_preview
      .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      .slice(0, 2);
    if (preview.length > 0) {
      summary.push(preview.join(" / "));
    }
  }

  return summary.slice(0, 3);
}

function renderCharacterCard(item: StoryCharacter) {
  return (
    <>
      <p className="text-sm font-semibold">{item.name}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">{item.personality ?? "暂无性格描述"}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
          状态：{item.status}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
          弧光：{item.arc_stage}
        </span>
      </div>
    </>
  );
}

function renderForeshadowCard(item: StoryForeshadow) {
  return (
    <>
      <p className="text-sm font-semibold">{item.content}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          埋设：{item.chapter_planted ?? "-"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          回收：{item.chapter_planned_reveal ?? "-"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          状态：{item.status}
        </span>
      </div>
    </>
  );
}

function renderItemCard(item: StoryItem) {
  return (
    <>
      <p className="text-sm font-semibold">{item.name}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">{item.features ?? "暂无物品特征"}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          归属：{item.owner ?? "未定"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          地点：{item.location ?? "未定"}
        </span>
      </div>
    </>
  );
}

function renderWorldRuleCard(item: StoryWorldRule) {
  return (
    <>
      <p className="text-sm font-semibold">{item.rule_name}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">{item.rule_content}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          范围：{item.scope}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          禁令：{item.negative_list.length} 条
        </span>
      </div>
    </>
  );
}

function renderTimelineCard(item: StoryTimelineMapEvent) {
  return (
    <>
      <p className="text-sm font-semibold">{item.core_event}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          章：{item.chapter_number ?? "-"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          地点：{item.location ?? "未定"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          天气：{item.weather ?? "未定"}
        </span>
      </div>
    </>
  );
}

function renderLocationCard(item: LocationItem) {
  const data = item.data ?? {};
  return (
    <>
      <p className="text-sm font-semibold">{item.name}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">
        {String(data.description ?? data.history ?? "暂无地点描述")}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          类型：{String(data.type ?? "未定")}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          气候：{String(data.climate ?? "未定")}
        </span>
      </div>
    </>
  );
}

function renderFactionCard(item: StoryBibleFactionEntry) {
  return (
    <>
      <p className="text-sm font-semibold">{item.name}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">{item.description ?? item.goals ?? "暂无势力描述"}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          类型：{item.type ?? "未定"}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          首领：{item.leader ?? "未定"}
        </span>
      </div>
    </>
  );
}

function renderPlotThreadCard(item: PlotThreadItem) {
  const data = item.data ?? {};
  return (
    <>
      <p className="text-sm font-semibold">{item.title}</p>
      <p className="mt-2 text-sm leading-7 text-black/62">
        {String(data.description ?? data.resolution ?? "暂无剧情线描述")}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          状态：{item.status}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1">
          权重：{item.importance}
        </span>
      </div>
    </>
  );
}

function resolveStoryBibleItemKey(item: Record<string, unknown>): string {
  for (const field of ["id", "key", "name", "title", "content"] as const) {
    const value = item[field];
    if (typeof value === "string" && value.trim().length > 0) {
      return `${field}:${value.trim()}`;
    }
  }
  return "";
}

function renderCard(tab: KnowledgeTabKey, item: Record<string, unknown>) {
  if (tab === "characters") {
    return renderCharacterCard(item as unknown as StoryCharacter);
  }
  if (tab === "foreshadows") {
    return renderForeshadowCard(item as unknown as StoryForeshadow);
  }
  if (tab === "items") {
    return renderItemCard(item as unknown as StoryItem);
  }
  if (tab === "locations") {
    return renderLocationCard(item as unknown as LocationItem);
  }
  if (tab === "factions") {
    return renderFactionCard(item as unknown as StoryBibleFactionEntry);
  }
  if (tab === "plot_threads") {
    return renderPlotThreadCard(item as unknown as PlotThreadItem);
  }
  if (tab === "world_rules") {
    return renderWorldRuleCard(item as unknown as StoryWorldRule);
  }
  return renderTimelineCard(item as unknown as StoryTimelineMapEvent);
}

function resolveList(
  workspace: StoryEngineWorkspace | null,
  storyBible: StoryBible | null,
  activeTab: KnowledgeTabKey,
): Record<string, unknown>[] {
  if (activeTab === "characters") {
    return (workspace?.characters ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "foreshadows") {
    return (workspace?.foreshadows ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "items") {
    return (workspace?.items ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "locations") {
    return (storyBible?.locations ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "factions") {
    return (storyBible?.factions ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "plot_threads") {
    return (storyBible?.plot_threads ?? []) as unknown as Record<string, unknown>[];
  }
  if (activeTab === "world_rules") {
    return (workspace?.world_rules ?? []) as unknown as Record<string, unknown>[];
  }
  return (workspace?.timeline_events ?? []) as unknown as Record<string, unknown>[];
}

export function KnowledgeBaseBoard({
  workspace,
  storyBible,
  activeTab,
  highlightedItemId,
  editingId,
  formState,
  saving,
  importing,
  searchQuery,
  searchResults,
  importTemplates,
  selectedTemplateKey,
  importPayloadText,
  replaceSections,
  generationLoadingKind,
  generationTask,
  generationTaskEvents,
  acceptingCandidateIndex,
  storyBibleVersions,
  storyBiblePendingChanges,
  loadingGovernance,
  governanceActionKey,
  onTabChange,
  onFieldChange,
  onSearchQueryChange,
  onImportTemplateChange,
  onImportPayloadChange,
  onToggleReplaceSection,
  onGenerateSuggestion,
  onAcceptSuggestion,
  onSearch,
  onSubmit,
  onSubmitImport,
  onStartEdit,
  onDelete,
  onJumpToRelatedChapter,
  onLocateSearchResult,
  onCancelEdit,
  onApprovePendingChange,
  onRejectPendingChange,
  onRollbackVersion,
}: KnowledgeBaseBoardProps) {
  const items = resolveList(workspace, storyBible, activeTab);
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const nodeLabelMap = new Map(
    (workspace?.relationship_graph.nodes ?? []).map((node) => [node.id, node.label]),
  );
  const selectedTemplate =
    importTemplates.find((item) => item.key === selectedTemplateKey) ?? null;
  const generationCards = extractSuggestionCards(generationTask);
  const visibleGenerationEvents = generationTaskEvents.slice(-5);
  const generationBusy =
    generationLoadingKind !== null ||
    generationTask?.status === "queued" ||
    generationTask?.status === "running";
  const visibleLocations = (storyBible?.locations ?? []).slice(0, 4);
  const visibleFactions = (storyBible?.factions ?? []).slice(0, 4);
  const visiblePlotThreads = (storyBible?.plot_threads ?? []).slice(0, 4);
  const activeTabLabel = TAB_LABELS[activeTab];

  function isGovernanceActionRunning(actionKey: string): boolean {
    return governanceActionKey === actionKey;
  }

  useEffect(() => {
    if (!highlightedItemId) {
      return;
    }
    const element = itemRefs.current[highlightedItemId];
    if (!element) {
      return;
    }
    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [activeTab, highlightedItemId, items.length]);

  return (
    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-copper">设定库</p>
            <h2 className="mt-2 text-2xl font-semibold">看设定、改设定</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(TAB_LABELS).map(([key, label]) => (
              <button
                key={key}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  activeTab === key
                    ? "bg-copper text-white"
                    : "border border-black/10 bg-white text-black/70 hover:bg-[#f6f0e6]"
                }`}
                onClick={() => onTabChange(key as KnowledgeTabKey)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            当前分类：{activeTabLabel}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            当前条目 {items.length} 条
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            待确认 {storyBiblePendingChanges.length} 条
          </span>
        </div>

        <div className="mt-6 grid gap-4">
          {items.length > 0 ? (
            items.map((item) => {
              const itemId = String(
                item.character_id ??
                item.foreshadow_id ??
                item.item_id ??
                item.rule_id ??
                item.event_id ??
                resolveStoryBibleItemKey(item)
              );
              return (
                <article
                  key={itemId}
                  ref={(node) => {
                    itemRefs.current[String(itemId)] = node;
                  }}
                  className={`rounded-[28px] border bg-[#fbfaf5] p-5 transition ${
                    highlightedItemId === String(itemId)
                      ? "border-copper shadow-[0_0_0_2px_rgba(173,91,50,0.12)]"
                      : "border-black/10"
                  }`}
                >
                  {renderCard(activeTab, item)}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/70"
                      onClick={() => onJumpToRelatedChapter(activeTab, item)}
                      type="button"
                    >
                      去正文定位
                    </button>
                    <button
                      className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/70"
                      onClick={() => onStartEdit(activeTab, item)}
                      type="button"
                    >
                      编辑
                    </button>
                    <button
                      className="rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700"
                      onClick={() => onDelete(activeTab, String(itemId))}
                      type="button"
                    >
                      删除
                    </button>
                  </div>
                </article>
              );
            })
          ) : (
            <div className="rounded-[28px] border border-dashed border-black/10 bg-[#fbfaf5] p-6 text-sm leading-7 text-black/45">
              当前分类还没有内容。
            </div>
          )}
        </div>
      </div>

      <aside className="space-y-4">
        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-copper">先确认</p>
              <h3 className="mt-2 text-lg font-semibold">待你确认的自动记设定</h3>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
                待确认 {storyBiblePendingChanges.length}
              </span>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
                可回退 {storyBibleVersions.length}
              </span>
            </div>
          </div>

          {loadingGovernance ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4 text-sm text-black/50">
              正在同步设定记录...
            </div>
          ) : null}

          <div className="mt-4 space-y-3">
            {storyBiblePendingChanges.length > 0 ? (
              storyBiblePendingChanges.slice(0, 4).map((change) => (
                <article
                  key={change.id}
                  className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{summarizeStoryBibleChange(change)}</p>
                      <p className="mt-2 text-xs text-black/45">
                        {formatStoryBibleChangeType(change.change_type)} ·{" "}
                        {formatStoryBibleChangeSource(change.change_source)} ·{" "}
                        {formatDateTime(change.created_at)}
                      </p>
                    </div>
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">
                      待确认
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-black/62">
                    {truncateText(
                      change.reason ??
                        extractStoryBibleEntityLabel(change.new_value) ??
                        extractStoryBibleEntityLabel(change.old_value) ??
                        "这条设定改动正在等待你确认。",
                      120,
                    )}
                  </p>
                  {change.proposed_by_agent ? (
                    <span className="mt-2 inline-flex rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] text-black/42">
                      {change.proposed_by_agent}
                    </span>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={isGovernanceActionRunning(`pending:approve:${change.id}`)}
                      onClick={() => onApprovePendingChange(change.id)}
                      type="button"
                    >
                      {isGovernanceActionRunning(`pending:approve:${change.id}`)
                        ? "确认中..."
                        : "确认收入设定"}
                    </button>
                    <button
                      className="rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={isGovernanceActionRunning(`pending:reject:${change.id}`)}
                      onClick={() => onRejectPendingChange(change.id)}
                      type="button"
                    >
                      {isGovernanceActionRunning(`pending:reject:${change.id}`)
                        ? "退回中..."
                        : "退回这条建议"}
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className="rounded-[24px] border border-dashed border-black/10 bg-[#fbfaf5] p-4 text-sm text-black/45">
                当前没有待确认设定。
              </div>
            )}
          </div>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-copper">当前在改</p>
              <h3 className="mt-2 text-lg font-semibold">
                {editingId ? `修改${activeTabLabel}` : `新增${activeTabLabel}`}
              </h3>
            </div>
            {editingId ? (
              <button
                className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/60"
                onClick={onCancelEdit}
                type="button"
              >
                取消
              </button>
            ) : null}
          </div>

          <div className="mt-4 grid gap-3">
            {activeTab === "characters" ? (
              <>
                <QuickField label="人物名" value={formState.name ?? ""} onChange={(value) => onFieldChange("name", value)} />
                <QuickField label="性格" value={formState.personality ?? ""} onChange={(value) => onFieldChange("personality", value)} multiline />
                <QuickField label="状态" value={formState.status ?? ""} onChange={(value) => onFieldChange("status", value)} />
                <QuickField label="弧光阶段" value={formState.arc_stage ?? ""} onChange={(value) => onFieldChange("arc_stage", value)} />
              </>
            ) : null}

            {activeTab === "foreshadows" ? (
              <>
                <QuickField label="伏笔内容" value={formState.content ?? ""} onChange={(value) => onFieldChange("content", value)} multiline />
                <QuickField label="埋设章节" value={formState.chapter_planted ?? ""} onChange={(value) => onFieldChange("chapter_planted", value)} />
                <QuickField label="计划回收章节" value={formState.chapter_planned_reveal ?? ""} onChange={(value) => onFieldChange("chapter_planned_reveal", value)} />
              </>
            ) : null}

            {activeTab === "items" ? (
              <>
                <QuickField label="物品名" value={formState.name ?? ""} onChange={(value) => onFieldChange("name", value)} />
                <QuickField label="特征" value={formState.features ?? ""} onChange={(value) => onFieldChange("features", value)} multiline />
                <QuickField label="当前归属" value={formState.owner ?? ""} onChange={(value) => onFieldChange("owner", value)} />
                <QuickField label="当前位置" value={formState.location ?? ""} onChange={(value) => onFieldChange("location", value)} />
              </>
            ) : null}

            {activeTab === "locations" ? (
              <>
                <QuickField label="地点名" value={formState.name ?? ""} onChange={(value) => onFieldChange("name", value)} />
                <QuickField label="地点类型" value={formState.location_type ?? ""} onChange={(value) => onFieldChange("location_type", value)} />
                <QuickField label="地点简介" value={formState.description ?? ""} onChange={(value) => onFieldChange("description", value)} multiline />
                <QuickField label="气候" value={formState.climate ?? ""} onChange={(value) => onFieldChange("climate", value)} />
                <QuickField label="人口 / 规模" value={formState.population ?? ""} onChange={(value) => onFieldChange("population", value)} />
                <QuickField label="显著特征（用 / 分隔）" value={formState.features ?? ""} onChange={(value) => onFieldChange("features", value)} />
                <QuickField label="常驻人物（用 / 分隔）" value={formState.notable_residents ?? ""} onChange={(value) => onFieldChange("notable_residents", value)} />
                <QuickField label="地点历史" value={formState.history ?? ""} onChange={(value) => onFieldChange("history", value)} multiline />
              </>
            ) : null}

            {activeTab === "factions" ? (
              <>
                <QuickField label="势力名" value={formState.name ?? ""} onChange={(value) => onFieldChange("name", value)} />
                <QuickField label="势力类型" value={formState.type ?? ""} onChange={(value) => onFieldChange("type", value)} />
                <QuickField label="势力简介" value={formState.description ?? ""} onChange={(value) => onFieldChange("description", value)} multiline />
                <QuickField label="规模" value={formState.scale ?? ""} onChange={(value) => onFieldChange("scale", value)} />
                <QuickField label="核心目标" value={formState.goals ?? ""} onChange={(value) => onFieldChange("goals", value)} multiline />
                <QuickField label="首领" value={formState.leader ?? ""} onChange={(value) => onFieldChange("leader", value)} />
                <QuickField label="主要成员（用 / 分隔）" value={formState.members ?? ""} onChange={(value) => onFieldChange("members", value)} />
                <QuickField label="控制范围" value={formState.territory ?? ""} onChange={(value) => onFieldChange("territory", value)} />
                <QuickField label="核心资源（用 / 分隔）" value={formState.resources ?? ""} onChange={(value) => onFieldChange("resources", value)} />
                <QuickField label="理念" value={formState.ideology ?? ""} onChange={(value) => onFieldChange("ideology", value)} multiline />
              </>
            ) : null}

            {activeTab === "plot_threads" ? (
              <>
                <QuickField label="剧情线标题" value={formState.title ?? ""} onChange={(value) => onFieldChange("title", value)} />
                <QuickField label="当前状态" value={formState.status ?? ""} onChange={(value) => onFieldChange("status", value)} />
                <QuickField label="重要度" value={formState.importance ?? ""} onChange={(value) => onFieldChange("importance", value)} />
                <QuickField label="剧情线类型" value={formState.plot_type ?? ""} onChange={(value) => onFieldChange("plot_type", value)} />
                <QuickField label="剧情线简介" value={formState.description ?? ""} onChange={(value) => onFieldChange("description", value)} multiline />
                <QuickField label="主导人物（用 / 分隔）" value={formState.main_characters ?? ""} onChange={(value) => onFieldChange("main_characters", value)} />
                <QuickField label="涉及地点（用 / 分隔）" value={formState.locations ?? ""} onChange={(value) => onFieldChange("locations", value)} />
                <QuickField label="推进阶段（用 / 分隔）" value={formState.stages ?? ""} onChange={(value) => onFieldChange("stages", value)} />
                <QuickField label="张力曲线" value={formState.tension_arc ?? ""} onChange={(value) => onFieldChange("tension_arc", value)} multiline />
                <QuickField label="计划收束" value={formState.resolution ?? ""} onChange={(value) => onFieldChange("resolution", value)} multiline />
              </>
            ) : null}

            {activeTab === "world_rules" ? (
              <>
                <QuickField label="规则名" value={formState.rule_name ?? ""} onChange={(value) => onFieldChange("rule_name", value)} />
                <QuickField label="规则内容" value={formState.rule_content ?? ""} onChange={(value) => onFieldChange("rule_content", value)} multiline />
                <QuickField label="适用范围" value={formState.scope ?? ""} onChange={(value) => onFieldChange("scope", value)} />
                <QuickField label="禁令清单（用 / 分隔）" value={formState.negative_list ?? ""} onChange={(value) => onFieldChange("negative_list", value)} />
              </>
            ) : null}

            {activeTab === "timeline_events" ? (
              <>
                <QuickField label="章节号" value={formState.chapter_number ?? ""} onChange={(value) => onFieldChange("chapter_number", value)} />
                <QuickField label="核心事件" value={formState.core_event ?? ""} onChange={(value) => onFieldChange("core_event", value)} multiline />
                <QuickField label="地点" value={formState.location ?? ""} onChange={(value) => onFieldChange("location", value)} />
                <QuickField label="天气" value={formState.weather ?? ""} onChange={(value) => onFieldChange("weather", value)} />
              </>
            ) : null}
          </div>

          <button
            className="mt-5 w-full rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={saving}
            onClick={onSubmit}
            type="button"
          >
            {saving ? "保存中..." : editingId ? "保存修改" : `新增${activeTabLabel}`}
          </button>
        </section>

        <details className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <summary className="cursor-pointer list-none text-lg font-semibold">更多设定工具</summary>

          <div className="mt-5 space-y-4">
            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <h3 className="text-sm font-semibold">灵感补全</h3>

              <div className="mt-4 flex flex-wrap gap-2">
                {GENERATION_ACTIONS.map((action) => (
                  <button
                    key={action.key}
                    className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                      generationLoadingKind === action.key
                        ? "bg-copper text-white"
                        : "border border-black/10 bg-white text-black/62 hover:bg-[#f6f0e6]"
                    }`}
                    disabled={generationBusy}
                    onClick={() => onGenerateSuggestion(action.key)}
                    type="button"
                  >
                    {generationLoadingKind === action.key ? "准备中..." : action.label}
                  </button>
                ))}
              </div>

              {generationTask ? (
                <div className="mt-4 rounded-[24px] border border-black/10 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">{formatGenerationTaskLabel(generationTask)}</p>
                    <span className="text-xs text-black/45">
                      {GENERATION_STATUS_LABELS[generationTask.status]} · {generationTask.progress}%
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-black/58">
                    {generationTask.message ?? "正在整理候选。"}
                  </p>
                </div>
              ) : null}

              {visibleGenerationEvents.length > 0 ? (
                <div className="mt-4 rounded-[24px] border border-black/10 bg-white p-4">
                  <p className="text-sm font-semibold">这轮补全进度</p>
                  <div className="mt-4 space-y-3">
                    {visibleGenerationEvents.map((event) => {
                      const summary = summarizeEntityGenerationEventPayload(event.payload);
                      return (
                        <article
                          key={event.id}
                          className="rounded-[18px] border border-black/8 bg-[#fbfaf5] px-3 py-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-xs font-semibold text-black/72">
                              {formatEntityGenerationEventLabel(event)}
                            </p>
                            <span className="text-[11px] text-black/42">
                              {formatDateTime(event.created_at)}
                            </span>
                          </div>
                          {summary.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {summary.map((item) => (
                                <span
                                  key={`${event.id}:${item}`}
                                  className="rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] text-black/52"
                                >
                                  {item}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              <div className="mt-4 space-y-3">
                {generationCards.length > 0 ? (
                  generationCards.map((card) => (
                    <article
                      key={card.title}
                      className="rounded-[24px] border border-black/10 bg-white p-4"
                    >
                      <p className="text-sm font-semibold">{card.title}</p>
                      <p className="mt-2 text-sm text-black/58">{card.detail}</p>
                      {card.canAccept ? (
                        <button
                          className="mt-3 rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={acceptingCandidateIndex === card.index}
                          onClick={() => onAcceptSuggestion(card.index)}
                          type="button"
                        >
                          {acceptingCandidateIndex === card.index ? "采纳中..." : "采纳进设定"}
                        </button>
                      ) : (
                        <span className="mt-3 inline-flex rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-[11px] text-black/45">
                          暂作灵感稿
                        </span>
                      )}
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-black/45">最近候选会显示在这里。</p>
                )}
              </div>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <h3 className="text-sm font-semibold">已记主设定</h3>

              <div className="mt-4 space-y-4">
                <div>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">地点</p>
                    <span className="text-xs text-black/45">{storyBible?.locations.length ?? 0} 条</span>
                  </div>
                  <div className="mt-3 grid gap-3">
                    {visibleLocations.length > 0 ? (
                      visibleLocations.map((item) =>
                        renderStoryBibleSummaryCard(
                          `location:${item.id ?? item.name}`,
                          item.name,
                          String(item.data.description ?? item.data.history ?? "已收入主设定。"),
                          [
                            item.data.type ? `类型：${String(item.data.type)}` : "",
                            item.data.climate ? `气候：${String(item.data.climate)}` : "",
                          ].filter(Boolean),
                        ),
                      )
                    ) : (
                      <p className="text-sm text-black/45">还没有地点。</p>
                    )}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">势力</p>
                    <span className="text-xs text-black/45">{storyBible?.factions.length ?? 0} 条</span>
                  </div>
                  <div className="mt-3 grid gap-3">
                    {visibleFactions.length > 0 ? (
                      visibleFactions.map((item) =>
                        renderStoryBibleSummaryCard(
                          `faction:${item.key}`,
                          item.name,
                          item.description ?? "已收入主设定。",
                          [
                            item.scale ? `规模：${item.scale}` : "",
                            item.leader ? `首领：${item.leader}` : "",
                          ].filter(Boolean),
                        ),
                      )
                    ) : (
                      <p className="text-sm text-black/45">还没有势力。</p>
                    )}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">剧情线</p>
                    <span className="text-xs text-black/45">{storyBible?.plot_threads.length ?? 0} 条</span>
                  </div>
                  <div className="mt-3 grid gap-3">
                    {visiblePlotThreads.length > 0 ? (
                      visiblePlotThreads.map((item) =>
                        renderStoryBibleSummaryCard(
                          `plot:${item.id ?? item.title}`,
                          item.title,
                          String(item.data.description ?? item.data.resolution ?? "已收入主设定。"),
                          [
                            item.status ? `状态：${item.status}` : "",
                            typeof item.importance === "number" ? `权重：${item.importance}` : "",
                          ].filter(Boolean),
                        ),
                      )
                    ) : (
                      <p className="text-sm text-black/45">还没有剧情线。</p>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <h3 className="text-sm font-semibold">导入整套设定</h3>

              <div className="mt-4 grid gap-3">
                <label className="block">
                  <FieldLabel label="模板" />
                  <select
                    className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                    value={selectedTemplateKey}
                    onChange={(event) => onImportTemplateChange(event.target.value)}
                  >
                    <option value="">只手动贴设定包</option>
                    {importTemplates.map((template) => (
                      <option key={template.key} value={template.key}>
                        {template.label}
                      </option>
                    ))}
                  </select>
                </label>

                {selectedTemplate ? (
                  <div className="rounded-[24px] border border-black/10 bg-white p-4">
                    <p className="text-sm font-semibold">{selectedTemplate.description}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedTemplate.usage_notes.map((note) => (
                        <span
                          key={note}
                          className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/58"
                        >
                          {note}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div>
                  <FieldLabel label="覆盖导入的区块" />
                  <div className="mt-2 flex flex-wrap gap-2">
                    {IMPORT_SECTION_OPTIONS.map((section) => {
                      const active = replaceSections.includes(section.key);
                      return (
                        <button
                          key={section.key}
                          className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                            active
                              ? "bg-copper text-white"
                              : "border border-black/10 bg-white text-black/62 hover:bg-[#f6f0e6]"
                          }`}
                          onClick={() => onToggleReplaceSection(section.key)}
                          type="button"
                        >
                          覆盖{section.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <label className="block">
                  <FieldLabel label="设定包内容" />
                  <textarea
                    className="mt-2 min-h-[220px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                    placeholder="把整套设定贴进来：人物、伏笔、物品、大纲都可以一起导入。"
                    value={importPayloadText}
                    onChange={(event) => onImportPayloadChange(event.target.value)}
                  />
                </label>
              </div>

              <button
                className="mt-5 w-full rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={importing || importPayloadText.trim().length === 0}
                onClick={onSubmitImport}
                type="button"
              >
                {importing ? "导入中..." : "导入整套设定"}
              </button>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <h3 className="text-sm font-semibold">搜设定</h3>
              <div className="mt-4 flex gap-2">
                <input
                  className="w-full rounded-full border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                  placeholder="搜人物口癖、旧伏笔、某条规则..."
                  value={searchQuery}
                  onChange={(event) => onSearchQueryChange(event.target.value)}
                />
                <button
                  className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/70"
                  onClick={onSearch}
                  type="button"
                >
                  搜一下
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {searchResults.length > 0 ? (
                  searchResults.map((item) => (
                    <article
                      key={`${item.entity_type}-${item.entity_id}`}
                      className="rounded-3xl border border-black/10 bg-white p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs uppercase tracking-[0.14em] text-copper">
                          {item.entity_type}
                        </span>
                        <span className="text-xs text-black/45">相关度 {item.score.toFixed(2)}</span>
                      </div>
                      <p className="mt-2 text-sm leading-7 text-black/62">{item.content}</p>
                      <button
                        className="mt-3 rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6]"
                        onClick={() => onLocateSearchResult(item)}
                        type="button"
                      >
                        定位条目
                      </button>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-black/45">输入关键词后开始搜索。</p>
                )}
              </div>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <h3 className="text-sm font-semibold">人物关系图</h3>
              <div className="mt-4 flex flex-wrap gap-2">
                {(workspace?.relationship_graph.nodes ?? []).map((node) => (
                  <span
                    key={node.id}
                    className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/62"
                  >
                    {node.label} · {node.arc_stage ?? "未定阶段"}
                  </span>
                ))}
              </div>
              <div className="mt-4 space-y-2">
                {(workspace?.relationship_graph.edges ?? []).length > 0 ? (
                  workspace?.relationship_graph.edges.map((edge, index) => (
                    <div
                      key={`${edge.source}-${edge.target}-${index}`}
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/62"
                    >
                      {nodeLabelMap.get(edge.source) ?? edge.source}
                      {" → "}
                      {nodeLabelMap.get(edge.target) ?? edge.target}
                      {"："}
                      {edge.relation}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-black/45">先给人物加关系。</p>
                )}
              </div>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold">最近设定版本</h3>
                <span className="text-xs text-black/45">{storyBibleVersions.length} 条</span>
              </div>
              <div className="mt-3 space-y-3">
                {storyBibleVersions.length > 0 ? (
                  storyBibleVersions.slice(0, 6).map((version) => (
                    <article
                      key={version.id}
                      className="rounded-[20px] border border-black/10 bg-white p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold">
                            V{version.version_number} · {summarizeStoryBibleChange(version)}
                          </p>
                          <p className="mt-2 text-xs text-black/45">
                            {formatStoryBibleChangeType(version.change_type)} ·{" "}
                            {formatStoryBibleChangeSource(version.change_source)} ·{" "}
                            {formatDateTime(version.created_at)}
                          </p>
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-7 text-black/62">
                        {truncateText(
                          version.note ??
                            extractStoryBibleEntityLabel(version.new_value) ??
                            extractStoryBibleEntityLabel(version.old_value) ??
                            "这版设定已经入库。",
                          120,
                        )}
                      </p>
                      <button
                        className="mt-3 rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={isGovernanceActionRunning(`version:rollback:${version.id}`)}
                        onClick={() => onRollbackVersion(version.id, version.version_number)}
                        type="button"
                      >
                        {isGovernanceActionRunning(`version:rollback:${version.id}`)
                          ? "回退中..."
                          : "退回这版设定"}
                      </button>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-black/45">还没有可回退版本。</p>
                )}
              </div>
            </section>
          </div>
        </details>
      </aside>
    </section>
  );
}
