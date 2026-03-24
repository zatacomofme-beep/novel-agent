"use client";

import type { FinalOptimizeResponse, StoryKnowledgeSuggestion } from "@/types/api";

type FinalDiffViewerProps = {
  result: FinalOptimizeResponse | null;
  resolvingSuggestionId: string | null;
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

export function FinalDiffViewer({
  result,
  resolvingSuggestionId,
  onApplyKnowledgeSuggestion,
  onIgnoreKnowledgeSuggestion,
}: FinalDiffViewerProps) {
  if (!result) {
    return (
      <section className="rounded-[36px] border border-dashed border-black/10 bg-white/70 p-8 text-sm leading-7 text-black/45">
        点击“优化爽点”后，这里会直接展示原稿和优化稿的对比、本章 100-300 字总结，以及自动沉淀下来的设定更新。
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

  return (
    <section className="space-y-6">
      <div className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-copper">终稿对比</p>
            <h2 className="mt-2 text-2xl font-semibold">看得到改了哪里，也看得到为什么改</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
              左边是你刚写完的原稿，右边是收敛后的可发版本。真正改动过的段落会被高亮。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62">
              已收口 {result.consensus_rounds} 轮
            </span>
            <span
              className={`rounded-full border px-3 py-2 text-xs ${
                result.ready_for_publish
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {result.ready_for_publish ? "可继续交稿" : `仍有 ${result.remaining_issue_count} 个问题`}
            </span>
            {result.revision_notes.map((note) => (
              <span
                key={note}
                className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/62"
              >
                {note}
              </span>
            ))}
          </div>
        </div>

        {result.quality_summary ? (
          <div className="mt-5 rounded-[24px] border border-[#d8c9b3] bg-[#fbf5ec] px-4 py-3 text-sm leading-7 text-black/68">
            {result.quality_summary}
          </div>
        ) : null}

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
            <h3 className="text-lg font-semibold">本章 100-300 字总结</h3>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              约 {summaryLength} 字
            </span>
          </div>
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
          <h3 className="text-lg font-semibold">设定更新清单</h3>
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
    </section>
  );
}
