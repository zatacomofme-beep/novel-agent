"use client";

import type { RefObject } from "react";

import { finalGateTone, formatCheckpointStatus, formatReviewVerdict } from "@/components/editor/formatters";
import type { Chapter, FinalOptimizeResponse, RealtimeGuardResponse, StoryOutline } from "@/types/api";

type PausedStreamState = {
  pausedAtParagraph: number;
  nextParagraphIndex: number;
  paragraphTotal: number;
  currentBeat: string | null;
  remainingBeats: string[];
};

type DraftStudioProps = {
  chapterNumber: number;
  chapterTitle: string;
  draftText: string;
  outlines: StoryOutline[];
  outlineSelectionId: string | null;
  activeChapter: Chapter | null;
  scopeLabel: string;
  savedChapterCount: number;
  guardResult: RealtimeGuardResponse | null;
  pausedStreamState: PausedStreamState | null;
  activeRepairInstruction: string | null;
  finalResult: FinalOptimizeResponse | null;
  checkingGuard: boolean;
  streaming: boolean;
  streamStatus: string | null;
  optimizing: boolean;
  savingDraft: boolean;
  draftDirty: boolean;
  editorTextareaRef: RefObject<HTMLTextAreaElement>;
  onChapterNumberChange: (value: number) => void;
  onChapterTitleChange: (value: string) => void;
  onDraftTextChange: (value: string) => void;
  onSelectOutlineId: (outlineId: string) => void;
  onSaveDraft: () => void;
  onRunStreamGenerate: () => void;
  onContinueWithRepair: (option: string) => void;
  onContinueAfterManualFix: () => void;
  onRunGuardCheck: () => void;
  onRunOptimize: () => void;
  onAutoRemember: () => void;
  onOpenOutlineStep: () => void;
};

const ALERT_TONES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-sky-200 bg-sky-50 text-sky-700",
};

function findChapterOutline(outlines: StoryOutline[], chapterNumber: number): StoryOutline | null {
  return outlines.find((item) => item.level === "level_3" && item.node_order === chapterNumber) ?? null;
}

function formatChapterStatus(status: string | null): string {
  const labels: Record<string, string> = {
    draft: "草稿箱",
    writing: "写作中",
    review: "待复核",
    final: "已终稿",
  };
  if (!status) {
    return "未保存";
  }
  return labels[status] ?? status;
}

function formatEvaluationStatus(status: string): string {
  const labels: Record<string, string> = {
    missing: "未检查",
    stale: "待重查",
    passed: "已通过",
    approved: "已通过",
    failed: "有问题",
    blocked: "有问题",
    pending: "检查中",
  };
  return labels[status] ?? status;
}

function formatPublishStatus(status: string): string {
  const labels: Record<string, string> = {
    ready: "可放行",
    blocked_pending: "待确认",
    blocked_rejected: "被驳回",
    blocked_checkpoint: "待重审",
    blocked_review: "需返修",
    blocked_evaluation: "待重查",
    blocked_integrity: "设定冲突",
    blocked_canon: "连续性冲突",
  };
  return labels[status] ?? status;
}

export function DraftStudio({
  chapterNumber,
  chapterTitle,
  draftText,
  outlines,
  outlineSelectionId,
  activeChapter,
  scopeLabel,
  savedChapterCount,
  guardResult,
  pausedStreamState,
  activeRepairInstruction,
  finalResult,
  checkingGuard,
  streaming,
  streamStatus,
  optimizing,
  savingDraft,
  draftDirty,
  editorTextareaRef,
  onChapterNumberChange,
  onChapterTitleChange,
  onDraftTextChange,
  onSelectOutlineId,
  onSaveDraft,
  onRunStreamGenerate,
  onContinueWithRepair,
  onContinueAfterManualFix,
  onRunGuardCheck,
  onRunOptimize,
  onAutoRemember,
  onOpenOutlineStep,
}: DraftStudioProps) {
  const currentOutline = findChapterOutline(outlines, chapterNumber);
  const level3OutlineOptions = outlines
    .filter((item) => item.level === "level_3")
    .sort((left, right) => left.node_order - right.node_order);
  const hasDraftText = draftText.trim().length > 0;
  const shouldShowGuard = Boolean(guardResult && guardResult.alerts.length > 0);
  const chapterStatusCardTone = activeChapter
    ? finalGateTone(activeChapter.final_gate_status)
    : "border-black/10 bg-white/88 text-black/72";

  return (
    <section className="grid gap-6 xl:grid-cols-[1.35fr_360px]">
      <div className="space-y-5">
        <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_20px_50px_rgba(16,20,23,0.05)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">第二步</p>
              <h2 className="mt-2 text-2xl font-semibold">生成正文</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={streaming || !currentOutline}
                onClick={onRunStreamGenerate}
                type="button"
              >
                {streaming ? "生成中..." : hasDraftText ? "继续生成正文" : "生成正文"}
              </button>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={streaming || savingDraft || (!draftDirty && activeChapter !== null)}
                onClick={onSaveDraft}
                type="button"
              >
                {savingDraft ? "保存中..." : draftDirty ? "保存本章" : "保存本章"}
              </button>
              <button
                className="rounded-full border border-black/10 bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={streaming || optimizing || !hasDraftText}
                onClick={onRunOptimize}
                type="button"
              >
                {optimizing ? "优化中..." : "检查并收口"}
              </button>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              {scopeLabel}
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              已存 {savedChapterCount} 章
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              {activeChapter ? `版本 V${activeChapter.current_version_number}` : "本章未保存"}
            </span>
            {draftDirty ? (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                有未保存改动
              </span>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-[1.2fr_0.8fr_1fr]">
            <label className="block md:col-span-3">
              <span className="text-sm text-black/60">先选这一章对应的三级大纲</span>
              <select
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                value={outlineSelectionId ?? ""}
                onChange={(event) => {
                  if (event.target.value) {
                    onSelectOutlineId(event.target.value);
                  }
                }}
              >
                <option value="">
                  {level3OutlineOptions.length === 0 ? "当前还没有三级大纲" : "先选一条三级大纲"}
                </option>
                {level3OutlineOptions.map((item) => (
                  <option key={item.outline_id} value={item.outline_id}>
                    第 {item.node_order} 章 · {item.title}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm text-black/60">章节号</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={1}
                value={chapterNumber}
                onChange={(event) => onChapterNumberChange(Number(event.target.value || 1))}
              />
            </label>

            <label className="block md:col-span-2">
              <span className="text-sm text-black/60">章节标题</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                value={chapterTitle}
                onChange={(event) => onChapterTitleChange(event.target.value)}
                placeholder="这一章叫什么？"
              />
            </label>
          </div>

          {!currentOutline ? (
            <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              这一章还没挂到三级大纲上。先回第一步补好，再生成正文会更稳。
              <button
                className="ml-3 rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-800"
                onClick={onOpenOutlineStep}
                type="button"
              >
                回第一步
              </button>
            </div>
          ) : null}

          {streamStatus ? (
            <div className="mt-5 rounded-[24px] border border-[#d8c9b3] bg-[#fbf5ec] px-4 py-3 text-sm text-black/68">
              {streamStatus}
            </div>
          ) : null}
        </section>

        <section className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
          <article className="rounded-[28px] border border-black/10 bg-white/82 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">本章章纲</h3>
              {currentOutline ? (
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                  第 {chapterNumber} 章
                </span>
              ) : null}
            </div>
            {currentOutline ? (
              <>
                <p className="mt-4 text-sm font-semibold text-black/82">{currentOutline.title}</p>
                <p className="mt-3 text-sm leading-7 text-black/62">{currentOutline.content}</p>
              </>
            ) : (
              <p className="mt-4 text-sm leading-7 text-black/52">选中三级大纲后，这里会显示本章推进节点。</p>
            )}

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                disabled={streaming}
                onClick={onRunGuardCheck}
                type="button"
              >
                {checkingGuard ? "检查中..." : "查人设 bug"}
              </button>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={streaming || !hasDraftText}
                onClick={onAutoRemember}
                type="button"
              >
                自动记设定
              </button>
            </div>
          </article>

          <label className="block rounded-[28px] border border-black/10 bg-white/82 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <span className="text-lg font-semibold">正文</span>
            <textarea
              ref={editorTextareaRef}
              className="mt-4 min-h-[560px] w-full rounded-[24px] border border-black/10 bg-[#fdfcf8] px-5 py-4 text-base leading-8 outline-none"
              placeholder="正文会从这里生成，你也可以直接手写。"
              value={draftText}
              onChange={(event) => onDraftTextChange(event.target.value)}
              disabled={streaming}
            />
          </label>
        </section>
      </div>

      <aside className="space-y-4">
        <section className={`rounded-[30px] border p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)] ${chapterStatusCardTone}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em]">本章状态</p>
              <h3 className="mt-2 text-lg font-semibold">
                {activeChapter ? formatPublishStatus(activeChapter.final_gate_status) : "待保存"}
              </h3>
            </div>
            <span className="rounded-full border border-current/20 px-3 py-1 text-xs">
              {formatChapterStatus(activeChapter?.status ?? null)}
            </span>
          </div>

          {activeChapter ? (
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-current/20 px-3 py-1">
                检查 {formatEvaluationStatus(activeChapter.latest_evaluation_status)}
              </span>
              <span className="rounded-full border border-current/20 px-3 py-1">
                待确认 {activeChapter.pending_checkpoint_count}
              </span>
              {activeChapter.latest_review_verdict ? (
                <span className="rounded-full border border-current/20 px-3 py-1">
                  复核 {formatReviewVerdict(activeChapter.latest_review_verdict)}
                </span>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7">先把正文生成出来，再保存本章。</p>
          )}

          {activeChapter?.latest_checkpoint_title ? (
            <div className="mt-4 rounded-[22px] border border-current/20 bg-white/70 px-4 py-3 text-sm">
              最近卡点：{activeChapter.latest_checkpoint_title}
              {activeChapter.latest_checkpoint_status
                ? ` · ${formatCheckpointStatus(activeChapter.latest_checkpoint_status)}`
                : ""}
            </div>
          ) : null}

          {activeChapter?.final_gate_reason ? (
            <div className="mt-4 rounded-[22px] border border-current/20 bg-white/70 px-4 py-3 text-sm leading-7">
              {activeChapter.final_gate_reason}
            </div>
          ) : null}
        </section>

        <section className="rounded-[30px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-copper">实时提醒</p>
              <h3 className="mt-2 text-lg font-semibold">
                {shouldShowGuard ? "这里有冲突要先修" : "当前没有明显冲突"}
              </h3>
            </div>
            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                shouldShowGuard
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-emerald-200 bg-emerald-50 text-emerald-700"
              }`}
            >
              {shouldShowGuard ? "需处理" : "安全"}
            </span>
          </div>

          {guardResult ? (
            <div className="mt-4 space-y-3">
              {guardResult.alerts.length > 0 ? (
                guardResult.alerts.map((alert) => (
                  <article
                    key={`${alert.title}-${alert.detail}`}
                    className={`rounded-[22px] border p-4 ${ALERT_TONES[alert.severity] ?? ALERT_TONES.low}`}
                  >
                    <p className="text-sm font-semibold">{alert.title}</p>
                    <p className="mt-2 text-sm leading-7">{alert.detail}</p>
                    {alert.suggestion ? (
                      <p className="mt-3 text-sm">修正建议：{alert.suggestion}</p>
                    ) : null}
                  </article>
                ))
              ) : (
                <div className="rounded-[22px] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                  当前正文没有发现硬冲突。
                </div>
              )}

              {guardResult.repair_options.length > 0 ? (
                <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-sm font-semibold">继续写之前，先选一个修法</p>
                  <div className="mt-3 space-y-2">
                    {guardResult.repair_options.map((option) => (
                      <button
                        key={option}
                        className={`w-full rounded-[18px] border px-3 py-3 text-left text-sm leading-7 transition ${
                          activeRepairInstruction === option && streaming
                            ? "border-copper bg-[#f6eee1] text-black"
                            : "border-black/10 bg-white text-black/68 hover:bg-[#f8f3ea]"
                        }`}
                        disabled={streaming}
                        onClick={() => onContinueWithRepair(option)}
                        type="button"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {pausedStreamState ? (
                <div className="rounded-[22px] border border-[#d8c9b3] bg-[#fbf5ec] p-4">
                  <p className="text-sm font-semibold">
                    已停在第 {pausedStreamState.pausedAtParagraph}/{pausedStreamState.paragraphTotal} 段
                  </p>
                  <button
                    className="mt-3 w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f8f3ea] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={streaming}
                    onClick={onContinueAfterManualFix}
                    type="button"
                  >
                    我已经改好，继续往下写
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-black/52">生成时只在真的发现冲突时提醒你。</p>
          )}
        </section>

        {finalResult ? (
          <section className="rounded-[30px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <p className="text-xs uppercase tracking-[0.18em] text-copper">本章总结</p>
            <p className="mt-3 text-sm leading-7 text-black/62">
              {finalResult.chapter_summary.content}
            </p>
          </section>
        ) : null}
      </aside>
    </section>
  );
}
