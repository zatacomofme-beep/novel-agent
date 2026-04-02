"use client";

import { useEffect, useMemo, useState } from "react";

import type {
  ProjectDeliveryCenter,
  ProjectDeliveryExportRequest,
  ProjectDeliveryExportRecord,
  ProjectDeliveryScope,
} from "@/types/api";

type DeliveryFormat = "md" | "txt";

type DeliveryCenterPanelProps = {
  deliveryCenter: ProjectDeliveryCenter | null;
  currentBranchId: string | null;
  currentVolumeId: string | null;
  loading: boolean;
  exportingKey: string | null;
  onExport: (payload: ProjectDeliveryExportRequest, scope: ProjectDeliveryScope) => void;
};

type DeliveryMetaFormState = {
  package_title: string;
  package_subtitle: string;
  author_name: string;
  synopsis: string;
  include_cover_page: boolean;
  include_metadata: boolean;
};

function formatWordCount(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "0";
  }
  if (value >= 10000) {
    return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}万`;
  }
  return value.toLocaleString("zh-CN");
}

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }
  const diffMs = Date.now() - date.getTime();
  if (diffMs <= 60_000) {
    return "刚刚";
  }
  const diffMinutes = Math.floor(diffMs / 60_000);
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }
  return `${Math.floor(diffHours / 24)} 天前`;
}

function dedupeScopes(scopes: Array<ProjectDeliveryScope | null>): ProjectDeliveryScope[] {
  const seen = new Set<string>();
  const result: ProjectDeliveryScope[] = [];
  for (const scope of scopes) {
    if (!scope || seen.has(scope.key)) {
      continue;
    }
    seen.add(scope.key);
    result.push(scope);
  }
  return result;
}

function buildVisibleScopes(
  deliveryCenter: ProjectDeliveryCenter | null,
  currentBranchId: string | null,
  currentVolumeId: string | null,
): ProjectDeliveryScope[] {
  if (!deliveryCenter) {
    return [];
  }

  const projectScope =
    deliveryCenter.scopes.find((scope) => scope.scope_kind === "project") ?? null;
  const finalPackageScope =
    deliveryCenter.scopes.find((scope) => scope.scope_kind === "final_package") ?? null;
  const currentBranchScope =
    currentBranchId
      ? deliveryCenter.scopes.find(
          (scope) => scope.scope_kind === "branch" && scope.branch_id === currentBranchId,
        ) ?? null
      : null;
  const currentVolumeScope =
    currentVolumeId
      ? deliveryCenter.scopes.find(
          (scope) => scope.scope_kind === "volume" && scope.volume_id === currentVolumeId,
        ) ?? null
      : null;

  return dedupeScopes([finalPackageScope, currentBranchScope, currentVolumeScope, projectScope]);
}

function buildScopeTone(scope: ProjectDeliveryScope, active: boolean): string {
  if (!scope.ready_for_delivery) {
    return active
      ? "border-black/15 bg-[#f3eee5]"
      : "border-black/10 bg-[#f8f4ec]";
  }
  if (active) {
    return "border-[#c8824d]/35 bg-[#f8efe3] shadow-[0_16px_40px_rgba(200,130,77,0.12)]";
  }
  if (scope.recommended) {
    return "border-[#c8824d]/20 bg-[#fbf2e6]";
  }
  return "border-black/10 bg-white";
}

function createMetaFormState(deliveryCenter: ProjectDeliveryCenter | null): DeliveryMetaFormState {
  return {
    package_title: deliveryCenter?.metadata_defaults.package_title ?? "",
    package_subtitle: deliveryCenter?.metadata_defaults.package_subtitle ?? "",
    author_name: deliveryCenter?.metadata_defaults.author_name ?? "",
    synopsis: deliveryCenter?.metadata_defaults.synopsis ?? "",
    include_cover_page: deliveryCenter?.metadata_defaults.include_cover_page ?? true,
    include_metadata: deliveryCenter?.metadata_defaults.include_metadata ?? true,
  };
}

function buildDefaultSelectedChapterIds(scope: ProjectDeliveryScope | null): string[] {
  if (!scope) {
    return [];
  }
  return scope.chapters
    .map((chapter) => chapter.id)
    .filter((chapterId): chapterId is string => Boolean(chapterId));
}

function buildExportSummaryLabel(record: ProjectDeliveryExportRecord): string {
  const title = record.package_title?.trim() || record.scope_label;
  const format = record.export_format === "md" ? "Markdown" : "TXT";
  return `${title} · ${format}`;
}

export function DeliveryCenterPanel({
  deliveryCenter,
  currentBranchId,
  currentVolumeId,
  loading,
  exportingKey,
  onExport,
}: DeliveryCenterPanelProps) {
  const visibleScopes = useMemo(
    () => buildVisibleScopes(deliveryCenter, currentBranchId, currentVolumeId),
    [deliveryCenter, currentBranchId, currentVolumeId],
  );
  const [activeScopeKey, setActiveScopeKey] = useState<string>("");
  const [chapterSelections, setChapterSelections] = useState<Record<string, string[]>>({});
  const [metaForm, setMetaForm] = useState<DeliveryMetaFormState>(() =>
    createMetaFormState(deliveryCenter),
  );

  useEffect(() => {
    setMetaForm(createMetaFormState(deliveryCenter));
  }, [deliveryCenter]);

  useEffect(() => {
    if (!visibleScopes.length) {
      setActiveScopeKey("");
      return;
    }

    const existing = visibleScopes.find((scope) => scope.key === activeScopeKey);
    if (existing) {
      return;
    }

    const preferredScope =
      visibleScopes.find((scope) => scope.key === deliveryCenter?.recommended_scope_key) ??
      visibleScopes.find((scope) => scope.recommended) ??
      visibleScopes[0];
    setActiveScopeKey(preferredScope.key);
  }, [activeScopeKey, deliveryCenter?.recommended_scope_key, visibleScopes]);

  useEffect(() => {
    if (!visibleScopes.length) {
      return;
    }

    setChapterSelections((current) => {
      const next = { ...current };
      let changed = false;
      for (const scope of visibleScopes) {
        if (next[scope.key] !== undefined) {
          continue;
        }
        next[scope.key] = buildDefaultSelectedChapterIds(scope);
        changed = true;
      }
      return changed ? next : current;
    });
  }, [visibleScopes]);

  const activeScope =
    visibleScopes.find((scope) => scope.key === activeScopeKey) ?? visibleScopes[0] ?? null;

  const chapterSelectionEnabled = Boolean(
    activeScope &&
      activeScope.chapters.length > 0 &&
      activeScope.chapters.every((chapter) => Boolean(chapter.id)),
  );

  const selectedChapterIds = activeScope
    ? chapterSelections[activeScope.key] ?? buildDefaultSelectedChapterIds(activeScope)
    : [];

  const selectedChapters = useMemo(() => {
    if (!activeScope) {
      return [];
    }
    if (!chapterSelectionEnabled) {
      return activeScope.chapters;
    }
    const selectedIds = new Set(selectedChapterIds);
    return activeScope.chapters.filter((chapter) => chapter.id && selectedIds.has(chapter.id));
  }, [activeScope, chapterSelectionEnabled, selectedChapterIds]);

  const selectedWordCount = selectedChapters.reduce(
    (total, chapter) => total + chapter.word_count,
    0,
  );

  function updateScopeSelection(scopeKey: string, nextIds: string[]) {
    setChapterSelections((current) => ({
      ...current,
      [scopeKey]: nextIds,
    }));
  }

  function toggleChapterSelection(chapterId: string) {
    if (!activeScope) {
      return;
    }
    const currentIds = chapterSelections[activeScope.key] ?? [];
    const currentSet = new Set(currentIds);
    if (currentSet.has(chapterId)) {
      currentSet.delete(chapterId);
    } else {
      currentSet.add(chapterId);
    }
    updateScopeSelection(activeScope.key, Array.from(currentSet));
  }

  function resetMetaForm() {
    setMetaForm(createMetaFormState(deliveryCenter));
  }

  function triggerExport(format: DeliveryFormat) {
    if (!activeScope) {
      return;
    }

    const exportRequest: ProjectDeliveryExportRequest = {
      format,
      scope: activeScope.scope_kind,
      branch_id: activeScope.branch_id,
      volume_id: activeScope.volume_id,
      chapter_ids: chapterSelectionEnabled ? selectedChapterIds : [],
      package_title: metaForm.package_title.trim() || null,
      package_subtitle: metaForm.package_subtitle.trim() || null,
      author_name: metaForm.author_name.trim() || null,
      synopsis: metaForm.synopsis.trim() || null,
      include_cover_page: metaForm.include_cover_page,
      include_metadata: metaForm.include_metadata,
    };
    onExport(exportRequest, activeScope);
  }

  return (
    <section className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-copper">交付中心</p>
          <h2 className="mt-2 text-2xl font-semibold">导出这部作品</h2>
        </div>
        {deliveryCenter ? (
          <div className="flex flex-wrap gap-2 text-xs text-black/55">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
              全书 {deliveryCenter.chapter_count} 章
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
              终稿 {deliveryCenter.final_chapter_count} 章
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
              导出记录 {deliveryCenter.recent_exports.length}
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
              {formatWordCount(deliveryCenter.total_word_count)} 字
            </span>
          </div>
        ) : null}
      </div>

      {loading && !deliveryCenter ? (
        <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-5 text-sm text-black/55">
          正在整理交付范围...
        </div>
      ) : null}

      {!loading && deliveryCenter && visibleScopes.length === 0 ? (
        <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-5 text-sm text-black/55">
          这本书还没有可导出的章节。
        </div>
      ) : null}

      {visibleScopes.length > 0 ? (
        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_380px]">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3">
              {visibleScopes.map((scope) => {
                const active = scope.key === activeScope?.key;
                return (
                  <button
                    key={scope.key}
                    type="button"
                    onClick={() => setActiveScopeKey(scope.key)}
                    className={`min-w-[168px] rounded-[24px] border px-4 py-4 text-left transition ${buildScopeTone(
                      scope,
                      active,
                    )}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-black/85">{scope.label}</p>
                        {scope.subtitle ? (
                          <p className="mt-1 text-xs text-black/55">{scope.subtitle}</p>
                        ) : null}
                      </div>
                      {scope.recommended ? (
                        <span className="rounded-full border border-[#c8824d]/25 bg-white px-2 py-1 text-[11px] text-[#9a5d32]">
                          推荐
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-black/55">
                      <span className="rounded-full border border-black/10 bg-white/80 px-2 py-1">
                        {scope.chapter_count} 章
                      </span>
                      <span className="rounded-full border border-black/10 bg-white/80 px-2 py-1">
                        {formatWordCount(scope.word_count)} 字
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {activeScope ? (
              <article className="rounded-[28px] border border-black/10 bg-[#fbfaf7] p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold">{activeScope.label}</h3>
                      <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                        {activeScope.ready_for_delivery ? "可导出" : "暂不可导出"}
                      </span>
                    </div>
                    {activeScope.description ? (
                      <p className="mt-2 text-sm text-black/55">{activeScope.description}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-black/55">
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      已选 {selectedChapters.length}/{activeScope.chapter_count}
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      终稿 {activeScope.final_chapter_count} 章
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      {formatWordCount(selectedWordCount || activeScope.word_count)} 字
                    </span>
                  </div>
                </div>

                {!activeScope.ready_for_delivery && activeScope.empty_reason ? (
                  <div className="mt-4 rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm text-black/55">
                    {activeScope.empty_reason}
                  </div>
                ) : null}

                {activeScope.ready_for_delivery && chapterSelectionEnabled ? (
                  <>
                    <div className="mt-5 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/65"
                        onClick={() =>
                          updateScopeSelection(activeScope.key, buildDefaultSelectedChapterIds(activeScope))
                        }
                      >
                        全选
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/65"
                        onClick={() =>
                          updateScopeSelection(
                            activeScope.key,
                            activeScope.chapters
                              .filter((chapter) => chapter.is_final && chapter.id)
                              .map((chapter) => chapter.id as string),
                          )
                        }
                      >
                        只选终稿
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/65"
                        onClick={() => updateScopeSelection(activeScope.key, [])}
                      >
                        清空
                      </button>
                    </div>

                    <div className="mt-4 max-h-[420px] space-y-2 overflow-y-auto pr-1">
                      {activeScope.chapters.map((chapter) => {
                        const checked = chapter.id ? selectedChapterIds.includes(chapter.id) : true;
                        return (
                          <label
                            key={`${activeScope.key}:${chapter.id ?? chapter.chapter_number}`}
                            className="flex cursor-pointer items-start gap-3 rounded-[20px] border border-black/10 bg-white px-4 py-3"
                          >
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4 rounded border-black/20 text-copper focus:ring-copper"
                              checked={checked}
                              onChange={() => {
                                if (chapter.id) {
                                  toggleChapterSelection(chapter.id);
                                }
                              }}
                              disabled={!chapter.id}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="truncate text-sm font-medium text-black/85">
                                  第 {chapter.chapter_number} 章
                                  {chapter.title ? ` · ${chapter.title}` : ""}
                                </p>
                                {chapter.is_final ? (
                                  <span className="rounded-full border border-[#c8824d]/20 bg-[#f8efe3] px-2 py-0.5 text-[11px] text-[#9a5d32]">
                                    终稿
                                  </span>
                                ) : null}
                              </div>
                              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-black/55">
                                {chapter.branch_title ? (
                                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1">
                                    {chapter.branch_title}
                                  </span>
                                ) : null}
                                {chapter.volume_title ? (
                                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1">
                                    {chapter.volume_title}
                                  </span>
                                ) : null}
                                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1">
                                  {chapter.status}
                                </span>
                                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1">
                                  {formatWordCount(chapter.word_count)} 字
                                </span>
                              </div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </>
                ) : null}

                <div className="mt-5 flex flex-wrap gap-3">
                  {(["md", "txt"] as DeliveryFormat[]).map((format) => {
                    const key = `${activeScope.key}:${format}`;
                    const disabled =
                      !activeScope.ready_for_delivery ||
                      exportingKey !== null ||
                      (chapterSelectionEnabled && selectedChapterIds.length === 0);
                    return (
                      <button
                        key={format}
                        type="button"
                        className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => triggerExport(format)}
                        disabled={disabled}
                      >
                        {exportingKey === key
                          ? "导出中..."
                          : format === "md"
                            ? "导出 Markdown"
                            : "导出 TXT"}
                      </button>
                    );
                  })}
                </div>
              </article>
            ) : null}
          </div>

          <div className="space-y-4">
            <article className="rounded-[28px] border border-black/10 bg-white p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-black/85">交稿信息</p>
                  <p className="mt-1 text-xs text-black/50">封面、署名、摘要</p>
                </div>
                <button
                  type="button"
                  className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/65"
                  onClick={resetMetaForm}
                >
                  恢复默认
                </button>
              </div>

              <div className="mt-4 space-y-3">
                <label className="block">
                  <span className="text-xs text-black/55">标题</span>
                  <input
                    value={metaForm.package_title}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        package_title: event.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper/50 focus:bg-white"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-black/55">副标题</span>
                  <input
                    value={metaForm.package_subtitle}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        package_subtitle: event.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper/50 focus:bg-white"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-black/55">署名</span>
                  <input
                    value={metaForm.author_name}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        author_name: event.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper/50 focus:bg-white"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-black/55">摘要</span>
                  <textarea
                    value={metaForm.synopsis}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        synopsis: event.target.value,
                      }))
                    }
                    rows={5}
                    className="mt-1 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper/50 focus:bg-white"
                  />
                </label>
              </div>

              <div className="mt-4 space-y-2">
                <label className="flex items-center justify-between rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm text-black/72">
                  <span>带封面页</span>
                  <input
                    type="checkbox"
                    checked={metaForm.include_cover_page}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        include_cover_page: event.target.checked,
                      }))
                    }
                    className="h-4 w-4 rounded border-black/20 text-copper focus:ring-copper"
                  />
                </label>
                <label className="flex items-center justify-between rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm text-black/72">
                  <span>带作品信息</span>
                  <input
                    type="checkbox"
                    checked={metaForm.include_metadata}
                    onChange={(event) =>
                      setMetaForm((current) => ({
                        ...current,
                        include_metadata: event.target.checked,
                      }))
                    }
                    className="h-4 w-4 rounded border-black/20 text-copper focus:ring-copper"
                  />
                </label>
              </div>
            </article>

            <article className="rounded-[28px] border border-black/10 bg-white p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-black/85">最近导出</p>
                  <p className="mt-1 text-xs text-black/50">最近 8 次</p>
                </div>
              </div>

              {deliveryCenter?.recent_exports.length ? (
                <div className="mt-4 space-y-3">
                  {deliveryCenter.recent_exports.map((record) => (
                    <div
                      key={record.id}
                      className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-black/82">
                            {buildExportSummaryLabel(record)}
                          </p>
                          <p className="mt-1 truncate text-xs text-black/50">
                            {record.filename}
                          </p>
                        </div>
                        <span className="shrink-0 text-[11px] text-black/45">
                          {formatRelativeTime(record.created_at)}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-black/55">
                        <span className="rounded-full border border-black/10 bg-white px-2 py-1">
                          {record.scope_label}
                        </span>
                        <span className="rounded-full border border-black/10 bg-white px-2 py-1">
                          {record.chapter_count} 章
                        </span>
                        <span className="rounded-full border border-black/10 bg-white px-2 py-1">
                          {formatWordCount(record.word_count)} 字
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-4 text-sm text-black/55">
                  还没有导出记录。
                </div>
              )}
            </article>
          </div>
        </div>
      ) : null}
    </section>
  );
}
