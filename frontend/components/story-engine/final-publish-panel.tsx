"use client";

import { buildFinalGateSummary, finalGateTone } from "@/components/editor/formatters";
import type { Chapter, FinalOptimizeResponse, ProjectNextChapterCandidate } from "@/types/api";

type ExportFormat = "md" | "txt";

type FinalPublishPanelProps = {
  activeChapter: Chapter | null;
  draftDirty: boolean;
  finalResult: FinalOptimizeResponse | null;
  nextChapter: ProjectNextChapterCandidate | null;
  carryoverPreview: string[];
  pendingKnowledgeCount: number;
  exportingFormat: ExportFormat | null;
  finalizingChapter: boolean;
  finalizingAction: "save" | "continue" | null;
  canApplyOptimizedDraft: boolean;
  onOpenDraftStep: () => void;
  onApplyOptimizedDraft: () => void;
  onSaveAsFinal: () => void;
  onSaveAsFinalAndContinue: () => void;
  onContinueToNextChapter: () => void;
  onExport: (format: ExportFormat) => void;
};

function buildStatusTitle(chapter: Chapter | null, finalResult: FinalOptimizeResponse | null): string {
  if (!chapter) {
    return "先保存正文";
  }
  if (chapter.status === "final") {
    return "这一章已确认";
  }
  if (!finalResult) {
    return "等待收口结果";
  }
  if (chapter.final_gate_status === "ready") {
    return "可以确认保存";
  }
  return "还需回正文处理";
}

function buildActionHint(chapter: Chapter | null, finalResult: FinalOptimizeResponse | null): string {
  if (!chapter) {
    return "先回正文区保存这一章。";
  }
  if (chapter.status === "final") {
    return "可以直接导出，也可以继续微调后重新确认。";
  }
  if (!finalResult) {
    return "先跑一次检查收口，再回来确认。";
  }
  if (finalResult) {
    if (!finalResult.ready_for_publish) {
      return finalResult.quality_summary ?? "这一轮还没完全收口，先看上面的修改点。";
    }
    return "先采纳优化稿，再确认保存这一章。";
  }
  if (chapter.final_gate_status === "ready") {
    return "可以确认保存。";
  }
  return "先继续润色。";
}

function buildNextChapterActionLabel(nextChapter: ProjectNextChapterCandidate | null): string {
  if (!nextChapter) {
    return "去下一章";
  }
  if (nextChapter.has_existing_content) {
    return `打开第 ${nextChapter.chapter_number} 章`;
  }
  return `去第 ${nextChapter.chapter_number} 章`;
}

function buildNextChapterDetail(nextChapter: ProjectNextChapterCandidate | null): string {
  if (!nextChapter) {
    return "当前还没有下一章入口。";
  }
  if (nextChapter.has_existing_content) {
    return "下一章已经有内容，切过去会继续带着上一章总结和设定往下写。";
  }
  if (nextChapter.generation_mode === "blueprint_seed") {
    return "下一章已经有章纲种子，切过去会带着上一章总结和设定直接起稿。";
  }
  if (nextChapter.based_on_blueprint) {
    return "系统已经给下一章预留好续写位，也会自动带上上一章总结。";
  }
  return "当前会按连续写作模式直接往下一章接，并继续沿用上一章总结。";
}

export function FinalPublishPanel({
  activeChapter,
  draftDirty,
  finalResult,
  nextChapter,
  carryoverPreview,
  pendingKnowledgeCount,
  exportingFormat,
  finalizingChapter,
  finalizingAction,
  canApplyOptimizedDraft,
  onOpenDraftStep,
  onApplyOptimizedDraft,
  onSaveAsFinal,
  onSaveAsFinalAndContinue,
  onContinueToNextChapter,
  onExport,
}: FinalPublishPanelProps) {
  const statusTone = finalGateTone(activeChapter?.final_gate_status ?? "blocked_pending");
  const canFinalizeChapter = Boolean(
    activeChapter &&
      (activeChapter.status === "final" || activeChapter.final_gate_status === "ready"),
  );
  const shouldReturnToDraft = !activeChapter || (!finalResult && activeChapter.status !== "final");
  const canExport = Boolean(activeChapter && (activeChapter.status === "final" || finalResult));
  const canContinueToNextChapter = Boolean(nextChapter && activeChapter?.status === "final");
  const flowCards = [
    {
      title: "看改动",
      status: finalResult ? "已完成" : "待处理",
      detail: finalResult ? "上方已经给出原稿和优化稿对比。" : "先生成收口结果。",
    },
    {
      title: "记设定",
      status: !finalResult ? "待处理" : pendingKnowledgeCount > 0 ? `${pendingKnowledgeCount} 条待确认` : "已完成",
      detail:
        !finalResult
          ? "收口完成后，这里会出现自动提取的设定更新。"
          : pendingKnowledgeCount > 0
          ? "上方还有自动提取的设定更新。"
          : "这一轮需要记入的设定已经处理完。",
    },
    {
      title: "确认保存",
      status: activeChapter?.status === "final" ? "已完成" : canFinalizeChapter ? "可确认" : "待处理",
      detail:
        activeChapter?.status === "final"
          ? "这一章已经存成终稿。"
          : canFinalizeChapter
            ? "采纳优化稿后就可以确认。"
            : "等收口通过后再确认。",
    },
    {
      title: "继续下一章",
      status: canContinueToNextChapter ? "已就位" : canFinalizeChapter ? "确认后可继续" : "待处理",
      detail: buildNextChapterDetail(nextChapter),
    },
  ];

  return (
    <section
      className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]"
      data-testid="final-publish-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-copper">第四步</p>
          <h2 className="mt-2 text-2xl font-semibold">确认保存这一章</h2>
        </div>
        {shouldReturnToDraft ? (
          <button
            className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            type="button"
            onClick={onOpenDraftStep}
          >
            回正文区继续
          </button>
        ) : null}
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-4">
        {flowCards.map((card) => (
          <article
            key={card.title}
            className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">{card.title}</p>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                {card.status}
              </span>
            </div>
            <p className="mt-2 text-xs leading-6 text-black/55">{card.detail}</p>
          </article>
        ))}
      </div>

      {draftDirty ? (
        <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-800">
          这一章还有未保存改动，先回正文区保存。
        </div>
      ) : null}

      {!activeChapter ? (
        <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/68">
          先把正文存成章节。
        </div>
      ) : !finalResult ? (
        <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/68">
          先跑出收口结果。
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <section className={`rounded-[28px] border p-5 ${statusTone}`}>
          <p className="text-sm font-semibold">现在</p>
          <h3 className="mt-2 text-2xl font-semibold">{buildStatusTitle(activeChapter, finalResult)}</h3>
          <p className="mt-3 text-sm leading-7">
            {buildFinalGateSummary(activeChapter)}
          </p>
          <div className="mt-4 rounded-[24px] border border-current/20 bg-white/70 px-4 py-3 text-sm leading-7">
            {buildActionHint(activeChapter, finalResult)}
          </div>
        </section>

        <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
          <p className="text-sm font-semibold">接下来</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={onApplyOptimizedDraft}
              disabled={!canApplyOptimizedDraft}
            >
              采纳优化稿
            </button>
            <button
              className="rounded-2xl bg-copper px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={onSaveAsFinal}
              disabled={!canFinalizeChapter || finalizingChapter}
            >
              {finalizingAction === "save"
                ? "处理中..."
                : activeChapter?.status === "final"
                  ? "重新确认终稿"
                  : "确认保存这一章"}
            </button>
            {activeChapter?.status === "final" ? (
              <button
                className="rounded-2xl bg-[#566246] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={onContinueToNextChapter}
                disabled={!canContinueToNextChapter || finalizingChapter}
                data-testid="final-continue-next-chapter"
              >
                {buildNextChapterActionLabel(nextChapter)}
              </button>
            ) : (
              <button
                className="rounded-2xl bg-[#566246] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={onSaveAsFinalAndContinue}
                disabled={!canFinalizeChapter || finalizingChapter}
              >
                {finalizingAction === "continue"
                  ? "处理中..."
                  : `确认并${buildNextChapterActionLabel(nextChapter)}`}
              </button>
            )}
          </div>

          {nextChapter ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/68">
              下一章：
              {`第 ${nextChapter.chapter_number} 章`}
              {nextChapter.title?.trim() ? ` · ${nextChapter.title.trim()}` : ""}
              。{buildNextChapterDetail(nextChapter)}
            </div>
          ) : null}

          {carryoverPreview.length > 0 ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-black/82">会自动带去下一章</p>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-[11px] text-black/55">
                  {carryoverPreview.length} 条
                </span>
              </div>
              <div className="mt-3 space-y-2">
                {carryoverPreview.map((item) => (
                  <div
                    key={item}
                    className="rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/65"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {pendingKnowledgeCount > 0 ? (
            <div className="mt-4 rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-800">
              还有 {pendingKnowledgeCount} 条设定建议待确认。下一章会先沿用已确认内容继续写，剩余建议你可以稍后再处理。
            </div>
          ) : null}

          <p className="mt-5 text-sm font-semibold">导出</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => onExport("md")}
              disabled={!canExport || exportingFormat !== null}
            >
              {exportingFormat === "md" ? "导出中..." : "导出 Markdown"}
            </button>
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium text-black/72 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => onExport("txt")}
              disabled={!canExport || exportingFormat !== null}
            >
              {exportingFormat === "txt" ? "导出中..." : "导出 TXT"}
            </button>
          </div>
          {finalResult?.revision_notes.length ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/68">
              本轮重点：{finalResult.revision_notes.slice(0, 2).join("；")}
            </div>
          ) : null}
          {finalResult?.quality_summary ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/68">
              收口结果：{finalResult.quality_summary}
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
