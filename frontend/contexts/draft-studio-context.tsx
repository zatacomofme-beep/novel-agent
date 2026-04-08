"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import type { Chapter, FinalOptimizeResponse, RealtimeGuardResponse, StoryOutline } from "@/types/api";
import type { StoryRoomLocalDraftRecoveryState } from "@/lib/story-room-local-draft";

export type PausedStreamState = {
  pausedAtParagraph: number;
  nextParagraphIndex: number;
  paragraphTotal: number;
  currentBeat: string | null;
  remainingBeats: string[];
};

export type RecoverableDraftCard = {
  storageKey: string;
  projectId: string;
  branchId: string | null;
  volumeId: string | null;
  chapterNumber: number;
  chapterTitle: string;
  outlineId: string | null;
  sourceChapterId: string | null;
  sourceVersionNumber: number | null;
  updatedAt: string;
  excerpt: string;
  charCount: number;
  storageEngine: "indexeddb" | "localStorage";
  scopeLabel: string;
  isCurrent: boolean;
};

export type DraftStudioCallbacks = {
  onChapterNumberChange: (value: number) => void;
  onChapterTitleChange: (value: string) => void;
  onDraftTextChange: (value: string) => void;
  onSelectOutlineId: (outlineId: string) => void;
  onJumpToChapter: (chapterNumber: number) => void;
  onSaveDraft: () => void;
  onRunStreamGenerate: () => void;
  onContinueWithRepair: (option: string) => void;
  onContinueAfterManualFix: () => void;
  onRunGuardCheck: () => void;
  onRunOptimize: () => void;
  onLocateSelectionInKnowledge: (selectionText: string) => void;
  onOpenOutlineStep: () => void;
  onOpenFinalStep: () => void;
  onOpenReviewTool: () => void;
  onOpenRecoverableDraft: (draft: RecoverableDraftCard) => void;
  onRestoreLocalDraft: () => void;
  onDismissLocalDraft: () => void;
  onRestoreCloudDraft: () => void;
  onDismissCloudDraft: () => void;
};

export type DraftStudioState = {
  chapterNumber: number;
  chapterTitle: string;
  draftText: string;
  outlines: StoryOutline[];
  scopeChapters: Chapter[];
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
  isOnline: boolean;
  localDraftSavedAt: string | null;
  localDraftRecoveredAt: string | null;
  pendingLocalDraftUpdatedAt: string | null;
  pendingLocalDraftRecoveryState: StoryRoomLocalDraftRecoveryState | null;
  cloudDraftSavedAt: string | null;
  cloudDraftRecoveredAt: string | null;
  pendingCloudDraftUpdatedAt: string | null;
  pendingCloudDraftRecoveryState: StoryRoomLocalDraftRecoveryState | null;
  cloudSyncing: boolean;
  cloudSyncEnabled: boolean;
  recoverableDrafts: RecoverableDraftCard[];
};

type DraftStudioContextValue = {
  state: DraftStudioState;
  callbacks: DraftStudioCallbacks;
  updateState: (patch: Partial<DraftStudioState>) => void;
};

const DraftStudioContext = createContext<DraftStudioContextValue | null>(null);

export function useDraftStudio() {
  const context = useContext(DraftStudioContext);
  if (!context) {
    throw new Error("useDraftStudio must be used within DraftStudioProvider");
  }
  return context;
}

export function DraftStudioProvider({
  initialState,
  callbacks,
  children,
}: {
  initialState: DraftStudioState;
  callbacks: DraftStudioCallbacks;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<DraftStudioState>(initialState);

  const updateState = useCallback((patch: Partial<DraftStudioState>) => {
    setState((prev) => ({ ...prev, ...patch }));
  }, []);

  const value = useMemo(
    () => ({ state, callbacks, updateState }),
    [state, callbacks, updateState],
  );

  return (
    <DraftStudioContext.Provider value={value}>
      {children}
    </DraftStudioContext.Provider>
  );
}
