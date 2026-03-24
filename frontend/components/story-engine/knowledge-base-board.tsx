"use client";

import { useEffect, useRef } from "react";

import type {
  LocationItem,
  PlotThreadItem,
  StoryBible,
  StoryCharacter,
  StoryEngineWorkspace,
  StoryBibleFactionEntry,
  StoryForeshadow,
  StoryImportTemplate,
  StoryItem,
  StorySearchResult,
  StoryTimelineMapEvent,
  StoryWorldRule,
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
  acceptingCandidateIndex: number | null;
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
  onCancelEdit: () => void;
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

function renderCard(tab: KnowledgeTabKey, item: any) {
  if (tab === "characters") {
    return renderCharacterCard(item);
  }
  if (tab === "foreshadows") {
    return renderForeshadowCard(item);
  }
  if (tab === "items") {
    return renderItemCard(item);
  }
  if (tab === "locations") {
    return renderLocationCard(item);
  }
  if (tab === "factions") {
    return renderFactionCard(item);
  }
  if (tab === "plot_threads") {
    return renderPlotThreadCard(item);
  }
  if (tab === "world_rules") {
    return renderWorldRuleCard(item);
  }
  return renderTimelineCard(item);
}

function resolveList(
  workspace: StoryEngineWorkspace | null,
  storyBible: StoryBible | null,
  activeTab: KnowledgeTabKey,
): any[] {
  if (activeTab === "characters") {
    return workspace?.characters ?? [];
  }
  if (activeTab === "foreshadows") {
    return workspace?.foreshadows ?? [];
  }
  if (activeTab === "items") {
    return workspace?.items ?? [];
  }
  if (activeTab === "locations") {
    return storyBible?.locations ?? [];
  }
  if (activeTab === "factions") {
    return storyBible?.factions ?? [];
  }
  if (activeTab === "plot_threads") {
    return storyBible?.plot_threads ?? [];
  }
  if (activeTab === "world_rules") {
    return workspace?.world_rules ?? [];
  }
  return workspace?.timeline_events ?? [];
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
  acceptingCandidateIndex,
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
  onCancelEdit,
}: KnowledgeBaseBoardProps) {
  const items = resolveList(workspace, storyBible, activeTab);
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const nodeLabelMap = new Map(
    (workspace?.relationship_graph.nodes ?? []).map((node) => [node.id, node.label]),
  );
  const selectedTemplate =
    importTemplates.find((item) => item.key === selectedTemplateKey) ?? null;
  const generationCards = extractSuggestionCards(generationTask);
  const generationBusy =
    generationLoadingKind !== null ||
    generationTask?.status === "queued" ||
    generationTask?.status === "running";
  const visibleLocations = (storyBible?.locations ?? []).slice(0, 4);
  const visibleFactions = (storyBible?.factions ?? []).slice(0, 4);
  const visiblePlotThreads = (storyBible?.plot_threads ?? []).slice(0, 4);

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
            <p className="text-xs uppercase tracking-[0.24em] text-copper">设定圣经</p>
            <h2 className="mt-2 text-2xl font-semibold">人物、伏笔、地点和剧情线都在这里收口</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
              你可以在这里统一管理人物、伏笔、物品、地点、势力、剧情线和规则设定。前台只保留一套面板，后台怎么分层保存都不用你操心。
            </p>
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

        <div className="mt-6 grid gap-4">
          {items.length > 0 ? (
            items.map((item) => {
              const itemId =
                item.character_id ??
                item.foreshadow_id ??
                item.item_id ??
                item.rule_id ??
                item.event_id ??
                resolveStoryBibleItemKey(item);
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
              当前分类还没有内容，右侧可以直接新增，或者先点上面的灵感补全。
            </div>
          )}
        </div>
      </div>

      <aside className="space-y-4">
        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">灵感补全</h3>
          <p className="mt-3 text-sm leading-7 text-black/52">
            卡设定时点一下就行，系统会先补几组候选给你挑，不会直接改掉你已经定下来的内容。
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            {GENERATION_ACTIONS.map((action) => (
              <button
                key={action.key}
                className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                  generationLoadingKind === action.key
                    ? "bg-copper text-white"
                    : "border border-black/10 bg-[#fbfaf5] text-black/62 hover:bg-white"
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
            <div className="mt-4 rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold">{formatGenerationTaskLabel(generationTask)}</p>
                <span className="text-xs text-black/45">
                  {GENERATION_STATUS_LABELS[generationTask.status]} · {generationTask.progress}%
                </span>
              </div>
              <p className="mt-2 text-sm leading-7 text-black/58">
                {generationTask.message ?? "正在整理这批候选。"}
              </p>
            </div>
          ) : null}

          <div className="mt-4 space-y-3">
            {generationCards.length > 0 ? (
              generationCards.map((card) => (
                <article
                  key={card.title}
                  className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4"
                >
                  <p className="text-sm font-semibold">{card.title}</p>
                  <p className="mt-2 text-sm leading-7 text-black/58">{card.detail}</p>
                  {card.canAccept ? (
                    <button
                      className="mt-3 rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={acceptingCandidateIndex === card.index}
                      onClick={() => onAcceptSuggestion(card.index)}
                      type="button"
                    >
                      {acceptingCandidateIndex === card.index ? "采纳中..." : "采纳进设定"}
                    </button>
                  ) : (
                    <p className="mt-3 text-xs leading-6 text-black/42">
                      这类候选暂时先当灵感稿使用，后面会继续补正式落库入口。
                    </p>
                  )}
                </article>
              ))
            ) : (
              <p className="text-sm leading-7 text-black/45">
                这里会挂出最近一轮补出来的候选，方便你直接拿去扩写或改成自己的版本。
              </p>
            )}
          </div>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">主设定补全结果</h3>
          <p className="mt-3 text-sm leading-7 text-black/52">
            新采纳的地点、势力、剧情线会先出现在这里，方便你不用切页就能确认主设定已经收进去。
          </p>

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
                  <p className="text-sm leading-7 text-black/45">还没有地点设定。</p>
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
                  <p className="text-sm leading-7 text-black/45">还没有势力设定。</p>
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
                  <p className="text-sm leading-7 text-black/45">还没有剧情线设定。</p>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">{editingId ? "编辑条目" : "新建条目"}</h3>
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
            {saving ? "保存中..." : editingId ? "保存修改" : "新增条目"}
          </button>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">导入整套设定</h3>
          <p className="mt-3 text-sm leading-7 text-black/52">
            想快速起盘时，可以直接套一整套设定骨架；也可以把你整理好的设定包整段贴进来。
          </p>

          <div className="mt-4 grid gap-3">
            <label className="block">
              <FieldLabel label="模板" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
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
              <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
                <p className="text-sm font-semibold">{selectedTemplate.description}</p>
                <div className="mt-3 space-y-2">
                  {selectedTemplate.usage_notes.map((note) => (
                    <p key={note} className="text-sm leading-7 text-black/58">
                      {note}
                    </p>
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
                          : "border border-black/10 bg-[#fbfaf5] text-black/62 hover:bg-white"
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
                className="mt-2 min-h-[220px] w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
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

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">搜设定</h3>
          <div className="mt-4 flex gap-2">
            <input
              className="w-full rounded-full border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
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
                  className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs uppercase tracking-[0.14em] text-copper">
                      {item.entity_type}
                    </span>
                    <span className="text-xs text-black/45">相关度 {item.score.toFixed(2)}</span>
                  </div>
                  <p className="mt-2 text-sm leading-7 text-black/62">{item.content}</p>
                </article>
              ))
            ) : (
              <p className="text-sm leading-7 text-black/45">
                输入关键词后，可以直接搜到旧设定，不用自己翻表。
              </p>
            )}
          </div>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">人物关系图</h3>
          <div className="mt-4 flex flex-wrap gap-2">
            {(workspace?.relationship_graph.nodes ?? []).map((node) => (
              <span
                key={node.id}
                className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62"
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
                  className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/62"
                >
                  {nodeLabelMap.get(edge.source) ?? edge.source}
                  {" → "}
                  {nodeLabelMap.get(edge.target) ?? edge.target}
                  {"："}
                  {edge.relation}
                </div>
              ))
            ) : (
              <p className="text-sm leading-7 text-black/45">
                先给人物加关系，这里就会自动长出关系线。
              </p>
            )}
          </div>
        </section>
      </aside>
    </section>
  );
}
