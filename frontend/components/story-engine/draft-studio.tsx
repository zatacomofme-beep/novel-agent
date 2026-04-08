"use client";

import type { MutableRefObject } from "react";

import type { DraftEditorHandle } from "@/components/story-engine/draft-editor-handle";
import { DraftEditorSurface } from "@/components/story-engine/draft-editor-surface";
import { buildOutlineNodes } from "@/components/story-engine/outline-node-utils";
import {
  finalGateTone,
  formatCheckpointStatus,
  formatDateTime,
  formatReviewVerdict,
} from "@/components/editor/formatters";
import {
  useDraftStudio,
  type RecoverableDraftCard,
} from "@/contexts/draft-studio-context";

type DraftStudioActionItem = {
  key: string;
  label: string;
  disabled: boolean;
  onClick: () => void;
  tone: "primary" | "secondary" | "accent";
};

type DraftStudioProps = {
  editorRef: MutableRefObject<DraftEditorHandle | null>;
};

const ALERT_TONES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-sky-200 bg-sky-50 text-sky-700",
};

const FLOW_STEP_TONES: Record<string, string> = {
  done: "border-emerald-200 bg-emerald-50",
  current: "border-copper/20 bg-[#fbf3e8]",
  pending: "border-black/10 bg-[#fbfaf5]",
};

function findChapterOutline(outlines: import("@/types/api").StoryOutline[], chapterNumber: number) {
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

function formatLocalDraftRecoveryTitle(
  state: import("@/lib/story-room-local-draft").StoryRoomLocalDraftRecoveryState | null,
): string {
  switch (state) {
    case "server_newer":
      return "发现更早版本留下的本机稿";
    case "local_newer":
      return "发现更新的本机稿";
    case "relinked":
      return "发现旧章节留下的本机稿";
    default:
      return "发现本机暂存";
  }
}

function formatLocalDraftRecoveryDetail(
  state: import("@/lib/story-room-local-draft").StoryRoomLocalDraftRecoveryState | null,
): string {
  switch (state) {
    case "server_newer":
      return "这份稿子来自更早的章节版本，恢复后会覆盖当前正文，先看一眼再决定。";
    case "local_newer":
      return "这份稿子比当前版本更新，适合直接接着往下写。";
    case "relinked":
      return "这一章的正式版本已经变过，本机稿还在，恢复前先确认内容是否要接回。";
    default:
      return "这份内容还没并进正式章节，恢复后就能继续写。";
  }
}

function formatCloudDraftRecoveryTitle(
  state: import("@/lib/story-room-local-draft").StoryRoomLocalDraftRecoveryState | null,
): string {
  switch (state) {
    case "server_newer":
      return "发现上一版留下的续写稿";
    case "local_newer":
      return "发现更新的续写稿";
    case "relinked":
      return "发现旧版本留下的续写稿";
    default:
      return "发现可接着写的续写稿";
  }
}

function formatCloudDraftRecoveryDetail(
  state: import("@/lib/story-room-local-draft").StoryRoomLocalDraftRecoveryState | null,
): string {
  switch (state) {
    case "server_newer":
      return "这份续写稿比当前正式版本更早，恢复前先看一眼，确认是不是你要接回的内容。";
    case "local_newer":
      return "这份续写稿比当前正式版本更新，恢复后就能继续往下写。";
    case "relinked":
      return "这一章的正式版本已经变过，但之前留下的续写稿还在，确认后可以重新接回。";
    default:
      return "这份续写稿会跟着账号带走，换台设备也能从这里继续写。";
  }
}

export function DraftStudio({ editorRef }: DraftStudioProps) {
  const { state, callbacks } = useDraftStudio();
  const {
    chapterNumber,
    chapterTitle,
    draftText,
    outlines,
    scopeChapters,
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
    isOnline,
    localDraftSavedAt,
    localDraftRecoveredAt,
    pendingLocalDraftUpdatedAt,
    pendingLocalDraftRecoveryState,
    cloudDraftSavedAt,
    cloudDraftRecoveredAt,
    pendingCloudDraftUpdatedAt,
    pendingCloudDraftRecoveryState,
    cloudSyncing,
    cloudSyncEnabled,
    recoverableDrafts,
  } = state;
  const {
    onChapterNumberChange,
    onChapterTitleChange,
    onDraftTextChange,
    onSelectOutlineId,
    onJumpToChapter,
    onSaveDraft,
    onRunStreamGenerate,
    onContinueWithRepair,
    onContinueAfterManualFix,
    onRunGuardCheck,
    onRunOptimize,
    onLocateSelectionInKnowledge,
    onOpenOutlineStep,
    onOpenFinalStep,
    onOpenReviewTool,
    onOpenRecoverableDraft,
    onRestoreLocalDraft,
    onDismissLocalDraft,
    onRestoreCloudDraft,
    onDismissCloudDraft,
  } = callbacks;

  const currentOutline = findChapterOutline(outlines, chapterNumber);
  const outlineNodes = buildOutlineNodes(currentOutline?.title ?? null, currentOutline?.content ?? null);
  const level3OutlineOptions = outlines
    .filter((item) => item.level === "level_3")
    .sort((left, right) => left.node_order - right.node_order);
  const hasDraftText = draftText.trim().length > 0;
  const isFirstDraft = !activeChapter && !hasDraftText;
  const shouldShowGuard = Boolean(guardResult && guardResult.alerts.length > 0);
  const hasFinalResult = finalResult !== null;
  const canSaveDraft = hasDraftText && !streaming && !savingDraft && (draftDirty || activeChapter === null);
  const canRunOptimize = Boolean(activeChapter) && hasDraftText && !draftDirty && !streaming && !optimizing;
  const otherRecoverableDrafts = recoverableDrafts
    .filter((item) => !item.isCurrent)
    .slice(0, 6);
  const currentHeading = chapterTitle.trim()
    ? `第 ${chapterNumber} 章 · ${chapterTitle.trim()}`
    : `第 ${chapterNumber} 章正文`;
  const chapterStatusCardTone = activeChapter
    ? finalGateTone(activeChapter.final_gate_status)
    : "border-black/10 bg-white/88 text-black/72";
  const currentDraftStage =
    hasFinalResult && !draftDirty
      ? "final-result"
      : !currentOutline
        ? "outline"
        : !hasDraftText
          ? "generate"
          : !activeChapter || draftDirty
            ? "save"
            : "finalize";
  const currentStepSummary = !currentOutline
    ? "先给这一章选好三级大纲。"
    : !hasDraftText
      ? "章纲已经就位，现在直接生成正文。"
      : !activeChapter || draftDirty
        ? "正文已经有了，先保存这一章。"
        : hasFinalResult
          ? "终稿结果已经出来了，确认后就能进入下一章。"
          : "本章已保存，下一步去检查收口。";

  const primaryAction: DraftStudioActionItem =
    currentDraftStage === "final-result"
      ? {
          key: "final",
          label: "去确认终稿",
          disabled: false,
          onClick: onOpenFinalStep,
          tone: "primary",
        }
      : currentDraftStage === "outline"
        ? {
            key: "outline",
            label: "先定本章三级大纲",
            disabled: false,
            onClick: onOpenOutlineStep,
            tone: "primary",
          }
        : currentDraftStage === "generate"
          ? {
              key: "generate",
              label: streaming ? "生成中..." : "生成正文",
              disabled: streaming,
              onClick: onRunStreamGenerate,
              tone: "primary",
            }
          : currentDraftStage === "save"
            ? {
                key: "save",
                label: savingDraft ? "保存中..." : "保存本章",
                disabled: !canSaveDraft,
                onClick: onSaveDraft,
                tone: "primary",
              }
            : {
                key: "optimize",
                label: optimizing ? "收口中..." : "检查并收口",
                disabled: !canRunOptimize,
                onClick: onRunOptimize,
                tone: "primary",
              };

  const secondaryActions: DraftStudioActionItem[] = [];
  if (currentDraftStage === "save" && currentOutline) {
    secondaryActions.push({
      key: "continue-generate",
      label: streaming ? "续写中..." : "继续写正文",
      disabled: streaming,
      onClick: onRunStreamGenerate,
      tone: "secondary",
    });
  }
  if (currentDraftStage === "finalize") {
    secondaryActions.push({
      key: "continue-generate",
      label: streaming ? "续写中..." : "继续写正文",
      disabled: streaming,
      onClick: onRunStreamGenerate,
      tone: "secondary",
    });
  }
  if ((currentDraftStage === "finalize" || currentDraftStage === "final-result") && activeChapter) {
    secondaryActions.push({
      key: "review",
      label: "去精修台",
      disabled: false,
      onClick: onOpenReviewTool,
      tone: currentDraftStage === "final-result" ? "accent" : "secondary",
    });
  }
  if (currentDraftStage === "final-result") {
    secondaryActions.unshift({
      key: "re-optimize",
      label: optimizing ? "收口中..." : "重新收口",
      disabled: !canRunOptimize,
      onClick: onRunOptimize,
      tone: "secondary",
    });
  }

  const visibleSecondaryActions = secondaryActions.slice(0, 2);

  const chapterFlowSteps: Array<{
    key: string;
    title: string;
    detail: string;
    state: "done" | "current" | "pending";
  }> = [
    {
      key: "outline",
      title: "章纲",
      detail: currentOutline ? `已挂第 ${currentOutline.node_order} 章` : "先选本章章纲",
      state: currentOutline ? "done" : "current",
    },
    {
      key: "draft",
      title: "正文",
      detail: hasDraftText ? `${draftText.trim().length} 字` : currentOutline ? "开始生成正文" : "等章纲就绪",
      state: hasDraftText ? "done" : currentOutline ? "current" : "pending",
    },
    {
      key: "save",
      title: "保存",
      detail:
        activeChapter && !draftDirty
          ? `版本 V${activeChapter.current_version_number}`
          : hasDraftText
            ? "先保存再收口"
            : "正文出来后保存",
      state: activeChapter && !draftDirty ? "done" : hasDraftText ? "current" : "pending",
    },
    {
      key: "final",
      title: "终稿",
      detail: hasFinalResult
        ? finalResult.ready_for_publish
          ? "可以确认"
          : "还有问题"
        : activeChapter && !draftDirty
          ? "下一步处理"
          : "保存后开启",
      state: hasFinalResult ? "done" : activeChapter && !draftDirty ? "current" : "pending",
    },
  ];

  const sidebarSections = (
    <>
      <section
        className={`rounded-[30px] border p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)] ${chapterStatusCardTone}`}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em]">本章进度</p>
            <h3 className="mt-2 text-lg font-semibold">
              {activeChapter ? formatPublishStatus(activeChapter.final_gate_status) : "待保存"}
            </h3>
          </div>
          <span className="rounded-full border border-current/20 px-3 py-1 text-xs">
            {formatChapterStatus(activeChapter?.status ?? null)}
          </span>
        </div>

        <div className="mt-4 space-y-3">
          {chapterFlowSteps.map((step) => (
            <div
              key={step.key}
              className="flex items-center justify-between gap-3 rounded-[20px] border border-current/20 bg-white/70 px-4 py-3"
            >
              <div>
                <p className="text-sm font-semibold">{step.title}</p>
                <p className="mt-1 text-xs opacity-75">{step.detail}</p>
              </div>
              <span className="rounded-full border border-current/20 px-3 py-1 text-[11px]">
                {step.state === "done" ? "已完成" : step.state === "current" ? "当前" : "待处理"}
              </span>
            </div>
          ))}
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
        ) : null}

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

        <button
          className="mt-4 w-full rounded-full bg-white/90 px-4 py-3 text-sm font-semibold text-black transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          disabled={primaryAction.disabled}
          onClick={primaryAction.onClick}
          type="button"
        >
          {primaryAction.label}
        </button>
      </section>

      <section className="rounded-[30px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-copper">写作保护</p>
            <h3 className="mt-2 text-lg font-semibold">
              {pendingLocalDraftUpdatedAt || pendingCloudDraftUpdatedAt
                ? "发现可续写版本"
                : cloudSyncEnabled
                  ? cloudSyncing
                    ? "正在顺手续存"
                    : "保稿已开启"
                  : "断网也会继续保稿"}
            </h3>
          </div>
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              isOnline
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-amber-200 bg-amber-50 text-amber-700"
            }`}
          >
            {isOnline ? "在线" : "离线"}
          </span>
        </div>

        <div className="mt-4 space-y-3">
          <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm text-black/62">
            {pendingLocalDraftUpdatedAt ? (
              <>
                <p className="font-semibold text-black/82">
                  {formatLocalDraftRecoveryTitle(pendingLocalDraftRecoveryState)}
                </p>
                <p className="mt-2 leading-7 text-black/62">
                  {formatLocalDraftRecoveryDetail(pendingLocalDraftRecoveryState)}
                </p>
                <p className="mt-2 text-xs text-black/52">
                  本机时间 {formatDateTime(pendingLocalDraftUpdatedAt)}
                </p>
              </>
            ) : (
              <>
                <p className="font-semibold text-black/82">
                  {isOnline
                    ? "你在这章里的改动会持续记在本机。"
                    : "当前断网，但你写下的内容还会继续留在本机。"}
                </p>
                {localDraftSavedAt ? (
                  <p className="mt-2 text-xs text-black/52">
                    最近保稿 {formatDateTime(localDraftSavedAt)}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-black/52">这一章一有内容就会自动保稿。</p>
                )}
              </>
            )}
          </div>

          {pendingLocalDraftUpdatedAt ? (
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-full bg-[#566246] px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90"
                onClick={onRestoreLocalDraft}
                data-testid="draft-restore-local"
                type="button"
              >
                恢复这章内容
              </button>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={onDismissLocalDraft}
                type="button"
              >
                忽略这份暂存
              </button>
            </div>
          ) : null}

          <div className="rounded-[22px] border border-black/10 bg-[#f6f8fc] px-4 py-3 text-sm text-black/62">
            {pendingCloudDraftUpdatedAt ? (
              <>
                <p className="font-semibold text-black/82">
                  {formatCloudDraftRecoveryTitle(pendingCloudDraftRecoveryState)}
                </p>
                <p className="mt-2 leading-7 text-black/62">
                  {formatCloudDraftRecoveryDetail(pendingCloudDraftRecoveryState)}
                </p>
                <p className="mt-2 text-xs text-black/52">
                  续写时间 {formatDateTime(pendingCloudDraftUpdatedAt)}
                </p>
              </>
            ) : (
              <>
                <p className="font-semibold text-black/82">
                  {cloudSyncEnabled
                    ? "联网时会顺手记一份续写稿，换设备也能从这一章继续。"
                    : "当前离线，等网络恢复后会继续保留跨设备续写。"}
                </p>
                {cloudDraftSavedAt ? (
                  <p className="mt-2 text-xs text-black/52">
                    最近续存 {formatDateTime(cloudDraftSavedAt)}
                    {cloudSyncing ? " · 正在更新" : ""}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-black/52">
                    {cloudSyncEnabled
                      ? "这一章一有改动，就会自动续存一份。"
                      : "网络恢复后，就会继续顺手续存。"}
                  </p>
                )}
              </>
            )}
          </div>

          {pendingCloudDraftUpdatedAt ? (
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-full bg-[#2f5d91] px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90"
                onClick={onRestoreCloudDraft}
                type="button"
              >
                恢复续写稿
              </button>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={onDismissCloudDraft}
                type="button"
              >
                清掉这份续写稿
              </button>
            </div>
          ) : null}

          {otherRecoverableDrafts.length > 0 ? (
            <div className="rounded-[22px] border border-black/10 bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-black/82">其他可恢复章节</p>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-[11px] text-black/55">
                  {otherRecoverableDrafts.length} 条
                </span>
              </div>
              <div className="mt-3 space-y-2">
                {otherRecoverableDrafts.map((draft) => (
                  <button
                    key={draft.storageKey}
                    className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-left transition hover:bg-white"
                    onClick={() => onOpenRecoverableDraft(draft)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-black/82">
                        第 {draft.chapterNumber} 章
                        {draft.chapterTitle.trim() ? ` · ${draft.chapterTitle.trim()}` : ""}
                      </p>
                      <span className="text-[11px] text-black/45">
                        {formatDateTime(draft.updatedAt)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-black/48">{draft.scopeLabel}</p>
                    {draft.excerpt ? (
                      <p className="mt-2 line-clamp-2 text-xs leading-6 text-black/58">
                        {draft.excerpt}
                      </p>
                    ) : null}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {localDraftRecoveredAt ? (
            <div className="rounded-[22px] border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
              已恢复本机稿 · {formatDateTime(localDraftRecoveredAt)}
            </div>
          ) : null}

          {cloudDraftRecoveredAt ? (
            <div className="rounded-[22px] border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
              已恢复续写稿 · {formatDateTime(cloudDraftRecoveredAt)}
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-[30px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-copper">实时提醒</p>
            <h3 className="mt-2 text-lg font-semibold">
              {shouldShowGuard ? "有冲突待修" : "当前无明显冲突"}
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
                  className={`rounded-[22px] border p-4 ${
                    ALERT_TONES[alert.severity] ?? ALERT_TONES.low
                  }`}
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
                <p className="text-sm font-semibold">选择修法</p>
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
        ) : null}
      </section>

      {finalResult ? (
        <section className="rounded-[30px] border border-black/10 bg-white/88 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <p className="text-xs uppercase tracking-[0.18em] text-copper">本章总结</p>
          <p className="mt-3 text-sm leading-7 text-black/62">{finalResult.chapter_summary.content}</p>
        </section>
      ) : null}
    </>
  );

  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]" data-testid="story-room-stage-draft">
      <div className="space-y-5">
        <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_20px_50px_rgba(16,20,23,0.05)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">第二步</p>
              <h2 className="mt-2 text-2xl font-semibold">{currentHeading}</h2>
              <p className="mt-2 text-sm leading-7 text-black/58">{currentStepSummary}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={primaryAction.disabled}
                onClick={primaryAction.onClick}
                type="button"
              >
                {primaryAction.label}
              </button>
              {visibleSecondaryActions.map((action) => (
                <button
                  key={action.key}
                  className={`rounded-full px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                    action.tone === "accent"
                      ? "border border-black/10 bg-[#566246] text-white hover:opacity-90"
                      : "border border-black/10 bg-white text-black/72 hover:bg-[#f6f0e6]"
                  }`}
                  disabled={action.disabled}
                  onClick={action.onClick}
                  type="button"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {chapterFlowSteps.map((step, index) => (
              <article
                key={step.key}
                className={`rounded-[24px] border px-4 py-4 ${FLOW_STEP_TONES[step.state]}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border border-black/10 bg-white text-xs font-semibold text-black/62">
                    {index + 1}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                    {step.state === "done" ? "已完成" : step.state === "current" ? "当前" : "待处理"}
                  </span>
                </div>
                <p className="mt-3 text-sm font-semibold text-black/82">{step.title}</p>
                <p className="mt-2 text-xs leading-6 text-black/58">{step.detail}</p>
              </article>
            ))}
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
            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                isOnline
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              }`}
            >
              {isOnline ? "联网正常" : "断网保护中"}
            </span>
            {draftDirty ? (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700">
                有未保存改动
              </span>
            ) : null}
            {cloudSyncing ? (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-sky-700">
                正在续存
              </span>
            ) : null}
            {localDraftSavedAt ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                本机已暂存
              </span>
            ) : null}
            {cloudDraftSavedAt ? (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-sky-700">
                换设备可续写
              </span>
            ) : null}
            {localDraftRecoveredAt ? (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-sky-700">
                已恢复暂存
              </span>
            ) : null}
            {cloudDraftRecoveredAt ? (
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-sky-700">
                已恢复续写稿
              </span>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-[1.15fr_0.85fr]">
            <label className="block">
              <span className="text-sm text-black/60">三级大纲</span>
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
                  {level3OutlineOptions.length === 0 ? "暂无三级大纲" : "选择三级大纲"}
                </option>
                {level3OutlineOptions.map((item) => (
                  <option key={item.outline_id} value={item.outline_id}>
                    第 {item.node_order} 章 · {item.title}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm text-black/60">章节标题</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                value={chapterTitle}
                onChange={(event) => onChapterTitleChange(event.target.value)}
                placeholder="这一章叫什么？"
                data-testid="draft-chapter-title-input"
              />
            </label>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-[180px_1fr]">
            <label className="block">
              <span className="text-sm text-black/60">章节号</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={1}
                value={chapterNumber}
                onChange={(event) => onChapterNumberChange(Number(event.target.value || 1))}
                data-testid="draft-chapter-number-input"
              />
            </label>
            <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3">
              <p className="text-sm text-black/55">当前章纲</p>
              {currentOutline ? (
                <>
                  <p className="mt-2 text-sm font-semibold text-black/84">{currentOutline.title}</p>
                  <p className="mt-2 line-clamp-3 text-sm leading-7 text-black/62">
                    {currentOutline.content}
                  </p>
                </>
              ) : (
                <p className="mt-2 text-sm text-black/52">先绑定这一章对应的三级大纲。</p>
              )}
            </div>
          </div>

          {currentOutline ? (
            <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-black/78">本章要写的节点</p>
                <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                  {outlineNodes.length > 0 ? `${outlineNodes.length} 个节点` : "已绑定章纲"}
                </span>
              </div>
              {outlineNodes.length > 0 ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {outlineNodes.map((node) => (
                    <article
                      key={node.key}
                      className="rounded-[20px] border border-black/10 bg-white px-4 py-4"
                    >
                      <p className="text-[11px] uppercase tracking-[0.16em] text-black/42">
                        节点 {node.index + 1}
                      </p>
                      <p className="mt-2 text-sm font-semibold text-black/82">{node.title}</p>
                      {node.summary !== node.title ? (
                        <p className="mt-2 text-xs leading-6 text-black/58">{node.summary}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm leading-7 text-black/58">
                  这章会按照当前三级大纲推进，你可以直接点上方按钮起稿。
                </p>
              )}
            </div>
          ) : null}

          {scopeChapters.length > 0 ? (
            <div className="mt-4 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-black/55">切换已写章节</p>
                <span className="text-xs text-black/45">{scopeChapters.length} 章</span>
              </div>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {scopeChapters.map((chapter) => {
                  const isActive = chapter.chapter_number === chapterNumber;
                  return (
                    <button
                      key={chapter.id}
                      className={`min-w-[144px] rounded-[18px] border px-3 py-3 text-left transition ${
                        isActive
                          ? "border-copper/20 bg-white text-black shadow-[0_10px_24px_rgba(176,112,53,0.08)]"
                          : "border-black/10 bg-white/80 text-black/70 hover:bg-white"
                      }`}
                      onClick={() => onJumpToChapter(chapter.chapter_number)}
                      type="button"
                    >
                      <p className="text-xs uppercase tracking-[0.14em] text-black/42">
                        第 {chapter.chapter_number} 章
                      </p>
                      <p className="mt-1 line-clamp-1 text-sm font-semibold">
                        {chapter.title?.trim() || "未命名章节"}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {!currentOutline ? (
            <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              当前章节还没绑定三级大纲。
              <button
                className="ml-3 rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-800"
                onClick={onOpenOutlineStep}
                type="button"
              >
                去绑定
              </button>
            </div>
          ) : null}

          {isFirstDraft && currentOutline ? (
            <div className="mt-5 rounded-[24px] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
              已挂到第 {currentOutline.node_order} 章章纲，点上方主按钮就会按这条章纲起稿。
            </div>
          ) : null}

          {streamStatus ? (
            <div className="mt-5 rounded-[24px] border border-[#d8c9b3] bg-[#fbf5ec] px-4 py-3 text-sm text-black/68">
              {streamStatus}
            </div>
          ) : null}
        </section>

        <section className="rounded-[28px] border border-black/10 bg-white/82 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">正文</h3>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                disabled={streaming || !hasDraftText}
                onClick={onRunGuardCheck}
                type="button"
              >
                {checkingGuard ? "检查中..." : "查人设 bug"}
              </button>
            </div>
          </div>

          <DraftEditorSurface
            value={draftText}
            disabled={streaming}
            placeholder="可直接生成，也可手写补改。"
            editorRef={editorRef}
            outlineTitle={currentOutline?.title ?? null}
            outlineContent={currentOutline?.content ?? null}
            onChange={onDraftTextChange}
            onLocateSelectionInKnowledge={onLocateSelectionInKnowledge}
          />
        </section>

        <details className="rounded-[28px] border border-black/10 bg-white/82 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)] md:hidden">
          <summary className="cursor-pointer list-none text-base font-semibold text-black/82">
            本章状态、保稿与提醒
          </summary>
          <div className="mt-4 space-y-4">{sidebarSections}</div>
        </details>
      </div>

      <aside className="hidden space-y-4 md:block">{sidebarSections}</aside>
    </section>
  );
}
