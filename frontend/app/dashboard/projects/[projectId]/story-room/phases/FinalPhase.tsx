"use client";

import { FinalDiffViewer } from "@/components/story-engine/final-diff-viewer";
import { FinalPublishPanel } from "@/components/story-engine/final-publish-panel";
import type {
  Chapter,
  FinalOptimizeResponse,
  StoryKnowledgeSuggestion,
  ProjectNextChapterCandidate,
} from "@/types/api";
import type { StoryRoomStageKey } from "../types";

type ExportFormat = "md" | "txt";

interface FinalPhaseProps {
  stage: StoryRoomStageKey;
  visibleFinalResult: FinalOptimizeResponse | null;
  draftText: string;
  activeChapter: Chapter | null;
  chapterTitle: string;
  resolvingSuggestionId: string | null;
  finalResult: FinalOptimizeResponse | null;
  nextChapterCandidate: ProjectNextChapterCandidate | null;
  currentChapterCarryoverPreview: string[];
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
  onApplyKnowledgeSuggestion: (suggestion: StoryKnowledgeSuggestion) => void;
  onIgnoreKnowledgeSuggestion: (suggestion: StoryKnowledgeSuggestion) => void;
}

export function FinalPhase({
  stage,
  visibleFinalResult,
  draftText,
  activeChapter,
  chapterTitle,
  resolvingSuggestionId,
  finalResult,
  nextChapterCandidate,
  currentChapterCarryoverPreview,
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
  onApplyKnowledgeSuggestion,
  onIgnoreKnowledgeSuggestion,
}: FinalPhaseProps) {
  if (stage !== "final") {
    return null;
  }

  return (
    <section
      id="story-stage-final"
      className="scroll-mt-6 space-y-4"
      data-testid="story-room-stage-final"
    >
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-4 py-3 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            第三步
          </span>
          <h2 className="text-lg font-semibold">终稿</h2>
          <span
            className={`rounded-full border px-3 py-1 text-xs ${
              visibleFinalResult
                ? visibleFinalResult.ready_for_publish
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
                : "border-black/10 bg-[#fbfaf5] text-black/60"
            }`}
          >
            {visibleFinalResult
              ? visibleFinalResult.ready_for_publish
                ? "可以交稿"
                : "还要确认"
              : "还没出结果"}
          </span>
        </div>
        {!visibleFinalResult ? (
          <button
            className="rounded-full bg-copper px-4 py-2 text-sm font-semibold text-white"
            onClick={onOpenDraftStep}
            type="button"
          >
            回正文区继续
          </button>
        ) : null}
      </div>

      <FinalDiffViewer
        result={visibleFinalResult}
        hasDraftText={draftText.trim().length > 0}
        hasSavedChapter={activeChapter !== null}
        chapterTitle={chapterTitle}
        resolvingSuggestionId={resolvingSuggestionId}
        onOpenDraftStep={onOpenDraftStep}
        onApplyKnowledgeSuggestion={onApplyKnowledgeSuggestion}
        onIgnoreKnowledgeSuggestion={onIgnoreKnowledgeSuggestion}
      />

      <FinalPublishPanel
        activeChapter={activeChapter}
        draftDirty={false}
        finalResult={finalResult}
        nextChapter={nextChapterCandidate}
        carryoverPreview={currentChapterCarryoverPreview}
        pendingKnowledgeCount={
          visibleFinalResult?.kb_update_list.filter(
            (item) => (item.status ?? "pending") === "pending",
          ).length ?? 0
        }
        exportingFormat={exportingFormat}
        finalizingChapter={finalizingChapter}
        finalizingAction={finalizingAction}
        canApplyOptimizedDraft={canApplyOptimizedDraft}
        onOpenDraftStep={onOpenDraftStep}
        onApplyOptimizedDraft={onApplyOptimizedDraft}
        onSaveAsFinal={onSaveAsFinal}
        onSaveAsFinalAndContinue={onSaveAsFinalAndContinue}
        onContinueToNextChapter={onContinueToNextChapter}
        onExport={onExport}
      />
    </section>
  );
}
