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
  styleSample: string;
  outlines: StoryOutline[];
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
  onStyleSampleChange: (value: string) => void;
  onSaveDraft: () => void;
  onRunStreamGenerate: () => void;
  onContinueWithRepair: (option: string) => void;
  onContinueAfterManualFix: () => void;
  onRunGuardCheck: () => void;
  onRunOptimize: () => void;
  onAutoRemember: () => void;
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
    final: "可发布",
  };
  if (!status) {
    return "未入主线";
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
    ready: "可发布",
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

function buildPublishSummary(chapter: Chapter | null): string {
  if (!chapter) {
    return "当前内容还只在编辑区里，点一次“保存正文”后，系统才会开始记版本、做复核和发布检查。";
  }
  if (chapter.final_gate_status === "ready") {
    return "这章已经纳入主线记录，当前发布条件是通过的，你可以继续润色，也可以走后续发布。";
  }
  if (chapter.final_gate_status === "blocked_evaluation") {
    return "这章刚发生过内容变动，最好先重新跑一轮完整检查，再决定是否放行。";
  }
  if (chapter.final_gate_status === "blocked_checkpoint" || chapter.final_gate_status === "blocked_pending") {
    return "这章还有待确认的问题没有收口，先处理完这些卡点，再继续往后推。";
  }
  if (chapter.final_gate_status === "blocked_review" || chapter.final_gate_status === "blocked_rejected") {
    return "这章目前还不适合放行，先按复核意见修一轮，会更稳。";
  }
  if (chapter.final_gate_status === "blocked_integrity" || chapter.final_gate_status === "blocked_canon") {
    return "这章在设定或连续性上还有硬伤，建议优先把冲突修平。";
  }
  return "这章已经进入主线记录，后续每次保存都会留下版本痕迹。";
}

export function DraftStudio({
  chapterNumber,
  chapterTitle,
  draftText,
  styleSample,
  outlines,
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
  onStyleSampleChange,
  onSaveDraft,
  onRunStreamGenerate,
  onContinueWithRepair,
  onContinueAfterManualFix,
  onRunGuardCheck,
  onRunOptimize,
  onAutoRemember,
}: DraftStudioProps) {
  const currentOutline = findChapterOutline(outlines, chapterNumber);
  const shouldShowGuard = guardResult && guardResult.alerts.length > 0;
  const isPaused = pausedStreamState !== null;
  const chapterStatusCardTone = activeChapter
    ? finalGateTone(activeChapter.final_gate_status)
    : "border-black/10 bg-white/88 text-black/72";

  return (
    <section className="grid gap-6 xl:grid-cols-[1.3fr_360px]">
      <div className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-copper">创作编辑器</p>
            <h2 className="mt-2 text-2xl font-semibold">专心写，危险设定由右侧盯住</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
              编辑区只保留写手真正需要看到的内容。后台校验再复杂，前台只会在真的有问题时提醒你。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={streaming || savingDraft || (!draftDirty && activeChapter !== null)}
              onClick={onSaveDraft}
              type="button"
            >
              {savingDraft ? "保存中..." : activeChapter ? (draftDirty ? "保存正文" : "已保存") : "保存正文"}
            </button>
            <button
              className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={streaming}
              onClick={onRunStreamGenerate}
              type="button"
            >
              {streaming ? "起稿中..." : draftText.trim() ? "继续往下写" : "开始出正文"}
            </button>
            <button
              className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
              disabled={streaming}
              onClick={onRunGuardCheck}
              type="button"
            >
              {checkingGuard ? "检查中..." : "查人设bug"}
            </button>
            <button
              className="rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={streaming || optimizing || draftText.trim().length === 0}
              onClick={onRunOptimize}
              type="button"
            >
              {optimizing ? "优化中..." : "优化爽点"}
            </button>
            <button
              className="rounded-full border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-white"
              disabled={streaming || draftText.trim().length === 0}
              onClick={onAutoRemember}
              type="button"
            >
              自动记设定
            </button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              activeChapter
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-black/10 bg-[#fbfaf5] text-black/55"
            }`}
          >
            {activeChapter ? "已纳入正式章节" : "还没存成正式章节"}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            {scopeLabel}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            当前已存 {savedChapterCount} 章
          </span>
          {activeChapter ? (
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              版本 V{activeChapter.current_version_number}
            </span>
          ) : null}
          {draftDirty ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
              有未保存改动
            </span>
          ) : null}
        </div>

        {streamStatus ? (
          <div className="mt-5 rounded-[24px] border border-[#d8c9b3] bg-[#fbf5ec] px-4 py-3 text-sm leading-7 text-black/68">
            {streamStatus}
          </div>
        ) : null}

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <label className="block">
            <span className="text-sm text-black/60">章节号</span>
            <input
              className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
              type="number"
              min={1}
              value={chapterNumber}
              onChange={(event) => onChapterNumberChange(Number(event.target.value || 1))}
            />
          </label>
          <label className="block md:col-span-2">
            <span className="text-sm text-black/60">章节标题</span>
            <input
              className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
              value={chapterTitle}
              onChange={(event) => onChapterTitleChange(event.target.value)}
              placeholder="这一章叫什么？"
            />
          </label>
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
          <label className="block">
            <span className="text-sm text-black/60">正文初稿</span>
            <textarea
              ref={editorTextareaRef}
              className="mt-2 min-h-[440px] w-full rounded-[28px] border border-black/10 bg-[#fdfcf8] px-5 py-4 text-base leading-8 outline-none"
              placeholder="像写 Word 一样直接写。右侧只有在真的发现冲突时才会提醒。"
              value={draftText}
              onChange={(event) => onDraftTextChange(event.target.value)}
              disabled={streaming}
            />
          </label>
          <div className="space-y-4">
            <section className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm font-semibold">本章当前细纲</p>
              <p className="mt-3 text-sm leading-7 text-black/62">
                {currentOutline?.content ?? "还没有找到对应章节的细纲，建议先去上方工作台补一条。"}
              </p>
            </section>
            <label className="block rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5">
              <span className="text-sm font-semibold">你的样文</span>
              <textarea
                className="mt-3 min-h-[180px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                placeholder="贴一段你自己的文字，系统会尽量守住你的句子节奏和气口。"
                value={styleSample}
                onChange={(event) => onStyleSampleChange(event.target.value)}
              />
            </label>
          </div>
        </div>
      </div>

      <aside className="space-y-4">
        <section className={`rounded-[32px] border p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)] ${chapterStatusCardTone}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em]">章节状态</p>
              <h3 className="mt-2 text-lg font-semibold">
                {activeChapter ? formatPublishStatus(activeChapter.final_gate_status) : "等你先存一次正文"}
              </h3>
            </div>
            <span className="rounded-full border border-current/20 px-3 py-1 text-xs">
              {activeChapter ? formatChapterStatus(activeChapter.status) : "未入主线"}
            </span>
          </div>

          <p className="mt-4 text-sm leading-7">{buildPublishSummary(activeChapter)}</p>

          {activeChapter ? (
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-current/20 px-3 py-1">
                版本 V{activeChapter.current_version_number}
              </span>
              <span className="rounded-full border border-current/20 px-3 py-1">
                待确认 {activeChapter.pending_checkpoint_count}
              </span>
              <span className="rounded-full border border-current/20 px-3 py-1">
                发布 {formatPublishStatus(activeChapter.final_gate_status)}
              </span>
              <span className="rounded-full border border-current/20 px-3 py-1">
                检查 {formatEvaluationStatus(activeChapter.latest_evaluation_status)}
              </span>
              {activeChapter.latest_review_verdict ? (
                <span className="rounded-full border border-current/20 px-3 py-1">
                  复核 {formatReviewVerdict(activeChapter.latest_review_verdict)}
                </span>
              ) : null}
            </div>
          ) : null}

          {activeChapter?.latest_checkpoint_title ? (
            <div className="mt-4 rounded-3xl border border-current/20 bg-white/60 px-4 py-3 text-sm">
              最近卡点：{activeChapter.latest_checkpoint_title}
              {activeChapter.latest_checkpoint_status
                ? ` · ${formatCheckpointStatus(activeChapter.latest_checkpoint_status)}`
                : ""}
            </div>
          ) : null}
          {activeChapter?.final_gate_reason ? (
            <div className="mt-4 rounded-3xl border border-current/20 bg-white/60 px-4 py-3 text-sm">
              <p className="font-semibold">当前要先处理什么</p>
              <p className="mt-2 leading-7">{activeChapter.final_gate_reason}</p>
            </div>
          ) : null}
          {activeChapter?.latest_review_summary ? (
            <div className="mt-4 rounded-3xl border border-current/20 bg-white/60 px-4 py-3 text-sm">
              <p className="font-semibold">最近复核意见</p>
              <p className="mt-2 leading-7">{activeChapter.latest_review_summary}</p>
            </div>
          ) : null}
          {activeChapter?.latest_story_bible_integrity_summary ? (
            <div className="mt-4 rounded-3xl border border-current/20 bg-white/60 px-4 py-3 text-sm">
              <p className="font-semibold">设定一致性提醒</p>
              <p className="mt-2 leading-7">{activeChapter.latest_story_bible_integrity_summary}</p>
            </div>
          ) : null}
          {activeChapter?.latest_canon_summary ? (
            <div className="mt-4 rounded-3xl border border-current/20 bg-white/60 px-4 py-3 text-sm">
              <p className="font-semibold">连续性提醒</p>
              <p className="mt-2 leading-7">{activeChapter.latest_canon_summary}</p>
            </div>
          ) : null}
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-copper">实时设定守护</p>
              <h3 className="mt-2 text-lg font-semibold">只在真冲突时打断你</h3>
            </div>
            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                shouldShowGuard
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-emerald-200 bg-emerald-50 text-emerald-700"
              }`}
            >
              {shouldShowGuard ? "需修正" : "安全"}
            </span>
          </div>

          {guardResult ? (
            <div className="mt-4 space-y-3">
              {guardResult.alerts.length > 0 ? (
                guardResult.alerts.map((alert) => (
                  <article
                    key={`${alert.title}-${alert.detail}`}
                    className={`rounded-3xl border p-4 ${ALERT_TONES[alert.severity] ?? ALERT_TONES.low}`}
                  >
                    <p className="text-sm font-semibold">{alert.title}</p>
                    <p className="mt-2 text-sm leading-7">{alert.detail}</p>
                    {alert.suggestion ? <p className="mt-3 text-sm">修正建议：{alert.suggestion}</p> : null}
                  </article>
                ))
              ) : (
                <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                  当前稿子没有发现硬冲突，可以继续写下去。
                </div>
              )}

              {guardResult.repair_options.length > 0 ? (
                <div className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-sm font-semibold">可选修法</p>
                  {pausedStreamState ? (
                    <p className="mt-2 text-sm leading-7 text-black/60">
                      目前停在第 {pausedStreamState.pausedAtParagraph}/{pausedStreamState.paragraphTotal} 段。
                      {pausedStreamState.nextParagraphIndex <= pausedStreamState.paragraphTotal
                        ? ` 选一条修法后，会从第 ${pausedStreamState.nextParagraphIndex} 段继续往下写。`
                        : " 这章主体已经顺完，修平这一处就可以收口。"}
                    </p>
                  ) : null}
                  <div className="mt-3 space-y-2">
                    {guardResult.repair_options.map((option) => (
                      <button
                        key={option}
                        className={`w-full rounded-2xl border px-3 py-3 text-left text-sm leading-7 transition ${
                          activeRepairInstruction === option && streaming
                            ? "border-copper bg-[#f6eee1] text-black"
                            : "border-black/10 bg-white text-black/68 hover:bg-[#f8f3ea]"
                        }`}
                        disabled={streaming}
                        onClick={() => onContinueWithRepair(option)}
                        type="button"
                      >
                        <span className="block font-semibold text-black/82">
                          {activeRepairInstruction === option && streaming ? "正在按这条修法续写..." : "按这条修法继续写"}
                        </span>
                        <span className="mt-1 block text-black/62">{option}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {isPaused ? (
                <div className="rounded-3xl border border-[#d8c9b3] bg-[#fbf5ec] p-4">
                  <p className="text-sm font-semibold">已经帮你停在安全位置</p>
                  <p className="mt-2 text-sm leading-7 text-black/62">
                    如果你刚刚已经手动把这段改好了，可以直接从停下的位置接着写，不会重头再来。
                  </p>
                  {pausedStreamState?.currentBeat ? (
                    <p className="mt-2 text-sm leading-7 text-black/52">
                      这一卡点对应的推进节点：{pausedStreamState.currentBeat}
                    </p>
                  ) : null}
                  <button
                    className="mt-3 w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f8f3ea] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={streaming}
                    onClick={onContinueAfterManualFix}
                    type="button"
                  >
                    {streaming && !activeRepairInstruction ? "正在继续..." : "我已经改好，继续往下写"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-7 text-black/52">
              写到一半也可以点一次“查人设bug”，右侧会立刻告诉你需不需要停下来修。
            </p>
          )}
        </section>

        {finalResult ? (
          <section className="rounded-[32px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <p className="text-xs uppercase tracking-[0.18em] text-copper">自动记设定</p>
            <h3 className="mt-2 text-lg font-semibold">本章已沉淀进设定库</h3>
            <p className="mt-3 text-sm leading-7 text-black/62">
              {finalResult.chapter_summary.content}
            </p>
          </section>
        ) : null}
      </aside>
    </section>
  );
}
