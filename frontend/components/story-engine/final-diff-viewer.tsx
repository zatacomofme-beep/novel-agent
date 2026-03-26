"use client";

import { StoryDeliberationPanel } from "@/components/story-engine/story-deliberation-panel";
import type { FinalOptimizeResponse, StoryKnowledgeSuggestion } from "@/types/api";

type FinalDiffViewerProps = {
  result: FinalOptimizeResponse | null;
  hasDraftText: boolean;
  hasSavedChapter: boolean;
  chapterTitle: string;
  resolvingSuggestionId: string | null;
  onOpenDraftStep: () => void;
  onApplyKnowledgeSuggestion: (suggestion: StoryKnowledgeSuggestion) => void;
  onIgnoreKnowledgeSuggestion: (suggestion: StoryKnowledgeSuggestion) => void;
};

function formatFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    entity_type: "类型",
    entity_key: "条目",
    action: "动作",
    name: "名称",
    title: "标题",
    content: "内容",
    status: "状态",
    summary: "摘要",
    chapter_number: "章节",
  };
  return labels[field] ?? field.replace(/_/g, " ");
}

function buildKnowledgeUpdatePreview(item: Record<string, unknown>): {
  title: string;
  detail: string;
} {
  const title =
    String(item.name ?? item.title ?? item.content ?? item.entity_key ?? "设定更新").trim() ||
    "设定更新";
  const detail = Object.entries(item)
    .filter(
      ([key, value]) =>
        ![
          "name",
          "title",
          "content",
          "suggestion_id",
          "status",
          "resolved_at",
          "applied_entity_type",
          "applied_entity_id",
          "applied_entity_key",
          "applied_entity_label",
        ].includes(key) &&
        value !== null &&
        value !== "",
    )
    .slice(0, 4)
    .map(([key, value]) => `${formatFieldLabel(key)}：${Array.isArray(value) ? value.join(" / ") : String(value)}`)
    .join("；");
  return {
    title,
    detail: detail || "这条更新已经收入设定圣经。",
  };
}

function splitParagraphs(text: string): string[] {
  return text
    .split(/\n{1,}/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function countChangedRows(
  rows: Array<{
    changed: boolean;
  }>,
): number {
  return rows.filter((row) => row.changed).length;
}

export function FinalDiffViewer({
  result,
  hasDraftText,
  hasSavedChapter,
  chapterTitle,
  resolvingSuggestionId,
  onOpenDraftStep,
  onApplyKnowledgeSuggestion,
  onIgnoreKnowledgeSuggestion,
}: FinalDiffViewerProps) {
  if (!result) {
    const chapterLabel = chapterTitle.trim() ? `《${chapterTitle.trim()}》` : "这一章";
    const heading = !hasDraftText
      ? "先写正文"
      : !hasSavedChapter
        ? "先保存正文"
        : `检查${chapterLabel}`;

    return (
      <section className="rounded-[36px] border border-dashed border-black/10 bg-white/74 p-8">
        <p className="text-xs uppercase tracking-[0.24em] text-copper">第三步</p>
        <h2 className="mt-2 text-2xl font-semibold">{heading}</h2>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4">
            <p className="text-sm font-semibold">保存正文</p>
            <p className="mt-2 text-xs leading-6 text-black/55">
              先把这一章存进项目，再进入收口。
            </p>
          </article>
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4">
            <p className="text-sm font-semibold">一键检查</p>
            <p className="mt-2 text-xs leading-6 text-black/55">
              系统会自动比对设定、逻辑和节奏。
            </p>
          </article>
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4">
            <p className="text-sm font-semibold">看改动</p>
            <p className="mt-2 text-xs leading-6 text-black/55">
              只需要看对比结果，再决定是否确认。
            </p>
          </article>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            onClick={onOpenDraftStep}
            type="button"
          >
            {hasDraftText ? "回正文区继续" : "回正文区开始写"}
          </button>
        </div>
      </section>
    );
  }

  const before = splitParagraphs(result.original_draft);
  const after = splitParagraphs(result.final_draft);
  const summaryLength = result.chapter_summary.content.trim().length;
  const maxLength = Math.max(before.length, after.length);
  const rows = Array.from({ length: maxLength }, (_, index) => ({
    before: before[index] ?? "",
    after: after[index] ?? "",
    changed: (before[index] ?? "") !== (after[index] ?? ""),
  }));
  const changedRowCount = countChangedRows(rows);
  const pendingKnowledgeCount = result.kb_update_list.filter(
    (item) => (item.status ?? "pending") === "pending",
  ).length;
  const revisionHighlights = result.revision_notes.slice(0, 3);

  return (
    <section className="space-y-6">
      <div className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-copper">第三步</p>
            <h2 className="mt-2 text-2xl font-semibold">收口结果</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62">
              收口 {result.consensus_rounds} 轮
            </span>
            <span
              className={`rounded-full border px-3 py-2 text-xs ${
                result.ready_for_publish
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {result.ready_for_publish ? "可以继续确认" : `还有 ${result.remaining_issue_count} 个问题`}
            </span>
            {revisionHighlights.map((note) => (
              <span
                key={note}
                className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62"
              >
                {note}
              </span>
            ))}
            {result.revision_notes.length > revisionHighlights.length ? (
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62">
                还有 {result.revision_notes.length - revisionHighlights.length} 条
              </span>
            ) : null}
          </div>
        </div>

        {result.quality_summary ? (
          <div className="mt-5 rounded-[24px] border border-[#d8c9b3] bg-[#fbf5ec] px-4 py-3 text-sm leading-7 text-black/68">
            {result.quality_summary}
          </div>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">当前结果</p>
            <p className="mt-2 text-2xl font-semibold">
              {result.ready_for_publish ? "可以确认" : "还需确认"}
            </p>
          </article>
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">修改段数</p>
            <p className="mt-2 text-2xl font-semibold">{changedRowCount} 段</p>
          </article>
          <article className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">待记设定</p>
            <p className="mt-2 text-2xl font-semibold">{pendingKnowledgeCount} 条</p>
          </article>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
            <h3 className="text-lg font-semibold">原稿</h3>
            <div className="mt-4 space-y-3">
              {rows.map((row, index) => (
                <article
                  key={`before-${index}`}
                  className={`rounded-3xl border p-4 text-sm leading-7 ${
                    row.changed
                      ? "border-amber-200 bg-amber-50 text-black/78"
                      : "border-black/10 bg-white text-black/62"
                  }`}
                >
                  {row.before || " "}
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
            <h3 className="text-lg font-semibold">优化稿</h3>
            <div className="mt-4 space-y-3">
              {rows.map((row, index) => (
                <article
                  key={`after-${index}`}
                  className={`rounded-3xl border p-4 text-sm leading-7 ${
                    row.changed
                      ? "border-emerald-200 bg-emerald-50 text-black/78"
                      : "border-black/10 bg-white text-black/62"
                  }`}
                >
                  {row.after || " "}
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-[30px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">会带去下一章的章节总结</h3>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              约 {summaryLength} 字
            </span>
          </div>
          <p className="mt-3 text-sm leading-7 text-black/52">
            确认保存后，下一章会优先读取这份总结，而不是只硬塞上一章原文。
          </p>
          <p className="mt-3 text-sm leading-7 text-black/62">{result.chapter_summary.content}</p>
          <div className="mt-4 space-y-2">
            {result.chapter_summary.core_progress.map((item) => (
              <div
                key={item}
                className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/62"
              >
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[30px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <h3 className="text-lg font-semibold">会回写进设定圣经的变动</h3>
          <p className="mt-3 text-sm leading-7 text-black/52">
            已确认的设定会直接进入后续章节上下文，待处理的建议可以在这里决定要不要记下。
          </p>
          <div className="mt-4 space-y-3">
            {result.kb_update_list.length > 0 ? (
              result.kb_update_list.map((item, index) => {
                const preview = buildKnowledgeUpdatePreview(item);
                const status = item.status ?? "pending";
                const busy = resolvingSuggestionId === item.suggestion_id;
                return (
                  <article
                    key={`${index}-${JSON.stringify(item)}`}
                    className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-4 text-sm leading-7 text-black/62"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-semibold text-black/78">{preview.title}</p>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs ${
                          status === "applied"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : status === "ignored"
                              ? "border-black/10 bg-white text-black/45"
                              : "border-amber-200 bg-amber-50 text-amber-700"
                        }`}
                      >
                        {status === "applied" ? "已记入" : status === "ignored" ? "已忽略" : "待处理"}
                      </span>
                    </div>
                    <p className="mt-2">{preview.detail}</p>
                    {status === "pending" ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          className="rounded-full bg-[#566246] px-3 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={busy}
                          onClick={() => onApplyKnowledgeSuggestion(item)}
                          type="button"
                        >
                          {busy ? "处理中..." : "记入设定"}
                        </button>
                        <button
                          className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/65 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={busy}
                          onClick={() => onIgnoreKnowledgeSuggestion(item)}
                          type="button"
                        >
                          先忽略
                        </button>
                      </div>
                    ) : null}
                  </article>
                );
              })
            ) : (
              <div className="rounded-3xl border border-dashed border-black/10 bg-[#fbfaf5] p-4 text-sm leading-7 text-black/50">
                这一轮没有新增需要回写的设定。
              </div>
            )}
          </div>
        </section>
      </div>

      <StoryDeliberationPanel
        title="这章怎么改的"
        rounds={result.deliberation_rounds}
        emptyText="这次终稿结果还没有可展开的推演纪要。"
      />
    </section>
  );
}
