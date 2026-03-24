"use client";

import { buildFinalGateSummary, finalGateTone } from "@/components/editor/formatters";
import type { Chapter, FinalOptimizeResponse } from "@/types/api";

type ExportFormat = "md" | "txt";

type FinalPublishPanelProps = {
  activeChapter: Chapter | null;
  draftDirty: boolean;
  finalResult: FinalOptimizeResponse | null;
  exportingFormat: ExportFormat | null;
  finalizingChapter: boolean;
  canApplyOptimizedDraft: boolean;
  onApplyOptimizedDraft: () => void;
  onSaveAsFinal: () => void;
  onExport: (format: ExportFormat) => void;
};

function buildStatusTitle(chapter: Chapter | null): string {
  if (!chapter) {
    return "先把正文存成正式章节";
  }
  if (chapter.status === "final") {
    return "这章已经处于终稿状态";
  }
  if (chapter.final_gate_status === "ready") {
    return "这章已经可以继续交稿";
  }
  return "这章还没到终稿状态";
}

function buildActionHint(chapter: Chapter | null, finalResult: FinalOptimizeResponse | null): string {
  if (!chapter) {
    return "保存正文后，系统才会正式记住这一章，并允许导出交稿版。";
  }
  if (chapter.status === "final") {
    return "当前已经是终稿，你可以直接导出交稿版。";
  }
  if (finalResult) {
    if (!finalResult.ready_for_publish) {
      return finalResult.quality_summary ?? "这轮深度校验还没完全收口，建议先按优化稿再顺一轮。";
    }
    return "如果这轮优化稿更顺手，先采纳优化稿，再决定是否标记终稿。";
  }
  if (chapter.final_gate_status === "ready") {
    return "正文状态已经稳定，可以直接尝试标记终稿。";
  }
  return "先继续润色或再跑一轮优化，等这章稳定后再标记终稿。";
}

export function FinalPublishPanel({
  activeChapter,
  draftDirty,
  finalResult,
  exportingFormat,
  finalizingChapter,
  canApplyOptimizedDraft,
  onApplyOptimizedDraft,
  onSaveAsFinal,
  onExport,
}: FinalPublishPanelProps) {
  const statusTone = finalGateTone(activeChapter?.final_gate_status ?? "blocked_pending");

  return (
    <section className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-copper">交稿动作</p>
          <h2 className="mt-2 text-2xl font-semibold">优化完就收口，不把后台流程摊给你看</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
            这里只保留你真正会点的几个动作：采纳优化稿、标记终稿、导出交稿版。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={onApplyOptimizedDraft}
            disabled={!canApplyOptimizedDraft}
          >
            采纳优化稿
          </button>
          <button
            className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={onSaveAsFinal}
            disabled={!activeChapter || finalizingChapter}
          >
            {finalizingChapter ? "处理中..." : activeChapter?.status === "final" ? "刷新终稿状态" : "标记终稿"}
          </button>
        </div>
      </div>

      {draftDirty ? (
        <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-800">
          当前正文还有未保存改动。先保存，再做终稿确认，会更稳。
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <section className={`rounded-[28px] border p-5 ${statusTone}`}>
          <p className="text-sm font-semibold">当前状态</p>
          <h3 className="mt-2 text-2xl font-semibold">{buildStatusTitle(activeChapter)}</h3>
          <p className="mt-3 text-sm leading-7">
            {buildFinalGateSummary(activeChapter)}
          </p>
          <div className="mt-4 rounded-[24px] border border-current/20 bg-white/70 px-4 py-3 text-sm leading-7">
            {buildActionHint(activeChapter, finalResult)}
          </div>
        </section>

        <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
          <p className="text-sm font-semibold">导出交稿版</p>
          <p className="mt-2 text-sm leading-7 text-black/62">
            导出时会直接带上当前正文内容。需要留档或交付时，点下面两个按钮即可。
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => onExport("md")}
              disabled={!activeChapter || exportingFormat !== null}
            >
              {exportingFormat === "md" ? "导出中..." : "导出 Markdown"}
            </button>
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => onExport("txt")}
              disabled={!activeChapter || exportingFormat !== null}
            >
              {exportingFormat === "txt" ? "导出中..." : "导出 TXT"}
            </button>
          </div>
          {finalResult?.revision_notes.length ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/68">
              最近优化重点：{finalResult.revision_notes.slice(0, 2).join("；")}
            </div>
          ) : null}
          {finalResult?.quality_summary ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/68">
              深度收口：{finalResult.quality_summary}
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
