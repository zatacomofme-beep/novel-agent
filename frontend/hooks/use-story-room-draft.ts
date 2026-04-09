"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import {
  analyzeStoryRoomLocalDraftRecovery,
  buildStoryRoomLocalDraftKey,
  listStoryRoomLocalDrafts,
  readStoryRoomLocalDraft,
  removeStoryRoomLocalDraft,
  summarizeStoryRoomLocalDraft,
  writeStoryRoomLocalDraft,
  type StoryRoomLocalDraftRecoveryState,
  type StoryRoomLocalDraftSnapshot,
  type StoryRoomLocalDraftSummary,
} from "@/lib/story-room-local-draft";
import type {
  Chapter,
  ChapterReviewWorkspace,
  ChapterVersion,
  FinalOptimizeResponse,
  ProjectStructure,
  RealtimeGuardResponse,
  StoryChapterSummary,
  StoryOutline,
  StoryRoomCloudDraft,
  StoryRoomCloudDraftSummary,
  StoryRoomCloudDraftUpsertRequest,
  UserPreferenceProfile,
} from "@/types/api";
import {
  createLegacyChapter,
  exportLegacyChapter,
  fetchLegacyChapterReviewBundle,
  rewriteLegacyChapterSelection,
  rollbackLegacyChapterVersion,
  updateLegacyChapter,
} from "@/lib/legacy-chapter-chain";

type UseStoryRoomDraftOptions = {
  projectId: string;
  chapterNumber: number;
  chapterTitle: string;
  draftText: string;
  outlineList: StoryOutline[];
  scopeChapters: Chapter[];
  selectedBranchId: string | null;
  selectedVolumeId: string | null;
  activeChapter: Chapter | null;
  currentOutline: StoryOutline | null;
  chapterSummaries: StoryChapterSummary[];
  onChapterTitleChange: (title: string) => void;
  onDraftTextChange: (text: string) => void;
  onSuccess: (message: string) => void;
  onError: (error: string) => void;
  onRefreshChapterChain: () => Promise<{ structureData: ProjectStructure; chapterData: Chapter[] }>;
  onLoadStyleControlState: (showSpinner?: boolean) => Promise<UserPreferenceProfile>;
  onLoadChapterReviewState: (chapterId: string, showSpinner?: boolean) => Promise<ChapterReviewWorkspace>;
};

type UseStoryRoomDraftReturn = {
  // 状态
  guardResult: RealtimeGuardResponse | null;
  pausedStreamState: Record<string, unknown> | null;
  activeRepairInstruction: string | null;
  finalResult: FinalOptimizeResponse | null;
  checkingGuard: boolean;
  streamingChapter: boolean;
  streamStatus: string | null;
  optimizing: boolean;
  savingDraft: boolean;
  draftDirty: boolean;
  isOnline: boolean;
  localDraftSavedAt: string | null;
  localDraftRecoveredAt: string | null;
  pendingLocalDraftSnapshot: StoryRoomLocalDraftSnapshot | null;
  pendingLocalDraftRecoveryState: StoryRoomLocalDraftRecoveryState | null;
  cloudDraftSavedAt: string | null;
  cloudDraftRecoveredAt: string | null;
  pendingCloudDraftSnapshot: StoryRoomCloudDraft | null;
  pendingCloudDraftRecoveryState: StoryRoomLocalDraftRecoveryState | null;
  cloudSyncing: boolean;
  exportingFormat: string | null;
  finalizingAction: string | null;
  reviewWorkspace: ChapterReviewWorkspace | null;
  chapterVersions: ChapterVersion[];
  loadingChapterReview: boolean;
  reviewSubmittingActionKey: string | null;
  recoverableLocalDrafts: StoryRoomLocalDraftSummary[];
  cloudDrafts: StoryRoomCloudDraftSummary[];
  currentLocalDraftKey: string | null;
  currentCloudDraftSummary: StoryRoomCloudDraftSummary | null;
  // 计算属性
  persistedChapterSummary: StoryChapterSummary | null;
  visibleFinalResult: FinalOptimizeResponse | null;
  canApplyOptimizedDraft: boolean;
  // 操作
  setDraftDirty: (dirty: boolean) => void;
  setGuardResult: (result: RealtimeGuardResponse | null) => void;
  setPausedStreamState: (state: Record<string, unknown> | null) => void;
  setFinalResult: (result: FinalOptimizeResponse | null) => void;
  setStreamStatus: (status: string | null) => void;
  setStreamingChapter: (streaming: boolean) => void;
  handleSaveDraft: () => Promise<void>;
  handleApplyOptimizedDraft: () => void;
  handleRestoreLocalDraft: () => void;
  handleDismissLocalDraft: () => void;
  handleRestoreCloudDraft: () => void;
  handleDismissCloudDraft: () => void;
  handleClearCurrentCloudDraft: () => Promise<void>;
  handleClearCurrentLocalDraft: () => Promise<void>;
};

function toLocalDraftSnapshotFromCloudDraft(draft: StoryRoomCloudDraft): StoryRoomLocalDraftSnapshot {
  return {
    projectId: draft.project_id,
    branchId: draft.branch_id,
    volumeId: draft.volume_id,
    chapterNumber: draft.chapter_number,
    chapterTitle: draft.chapter_title,
    draftText: draft.draft_text,
    outlineId: draft.outline_id,
    sourceChapterId: draft.source_chapter_id,
    sourceVersionNumber: draft.source_version_number,
    updatedAt: draft.updated_at,
  };
}

function buildCloudDraftScopeKey(
  branchId: string | null,
  volumeId: string | null,
  chapterNumber: number,
): string {
  return `${branchId ?? "default"}:${volumeId ?? "default"}:${chapterNumber}`;
}

function buildChapterOutlinePayload(outline: StoryOutline | null): Record<string, unknown> | null {
  if (!outline) {
    return null;
  }
  return {
    outline_id: outline.outline_id,
    parent_id: outline.parent_id,
    level: outline.level,
    title: outline.title,
    content: outline.content,
    status: outline.status,
    version: outline.version,
    node_order: outline.node_order,
    locked: outline.locked,
  };
}

export function useStoryRoomDraft({
  projectId,
  chapterNumber,
  chapterTitle,
  draftText,
  outlineList,
  scopeChapters,
  selectedBranchId,
  selectedVolumeId,
  activeChapter,
  currentOutline,
  chapterSummaries,
  onChapterTitleChange,
  onDraftTextChange,
  onSuccess,
  onError,
  onRefreshChapterChain,
  onLoadStyleControlState,
  onLoadChapterReviewState,
}: UseStoryRoomDraftOptions): UseStoryRoomDraftReturn {
  // 状态
  const [guardResult, setGuardResult] = useState<RealtimeGuardResponse | null>(null);
  const [pausedStreamState, setPausedStreamState] = useState<any | null>(null);
  const [activeRepairInstruction, setActiveRepairInstruction] = useState<string | null>(null);
  const [finalResult, setFinalResult] = useState<FinalOptimizeResponse | null>(null);
  const [checkingGuard, setCheckingGuard] = useState(false);
  const [streamingChapter, setStreamingChapter] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [localDraftSavedAt, setLocalDraftSavedAt] = useState<string | null>(null);
  const [localDraftRecoveredAt, setLocalDraftRecoveredAt] = useState<string | null>(null);
  const [pendingLocalDraftSnapshot, setPendingLocalDraftSnapshot] = useState<StoryRoomLocalDraftSnapshot | null>(null);
  const [pendingLocalDraftRecoveryState, setPendingLocalDraftRecoveryState] = useState<StoryRoomLocalDraftRecoveryState | null>(null);
  const [cloudDraftSavedAt, setCloudDraftSavedAt] = useState<string | null>(null);
  const [cloudDraftRecoveredAt, setCloudDraftRecoveredAt] = useState<string | null>(null);
  const [pendingCloudDraftSnapshot, setPendingCloudDraftSnapshot] = useState<StoryRoomCloudDraft | null>(null);
  const [pendingCloudDraftRecoveryState, setPendingCloudDraftRecoveryState] = useState<StoryRoomLocalDraftRecoveryState | null>(null);
  const [cloudSyncing, setCloudSyncing] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [finalizingAction, setFinalizingAction] = useState<string | null>(null);
  const [reviewWorkspace, setReviewWorkspace] = useState<ChapterReviewWorkspace | null>(null);
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([]);
  const [loadingChapterReview, setLoadingChapterReview] = useState(false);
  const [reviewSubmittingActionKey, setReviewSubmittingActionKey] = useState<string | null>(null);
  const [recoverableLocalDrafts, setRecoverableLocalDrafts] = useState<StoryRoomLocalDraftSummary[]>([]);
  const [cloudDrafts, setCloudDrafts] = useState<StoryRoomCloudDraftSummary[]>([]);

  const editorRef = useRef<any>(null);

  // 计算属性
  const currentLocalDraftKey = useMemo(() => {
    return buildStoryRoomLocalDraftKey({
      projectId,
      branchId: selectedBranchId,
      volumeId: selectedVolumeId,
      chapterNumber,
    });
  }, [chapterNumber, projectId, selectedBranchId, selectedVolumeId]);

  const currentCloudDraftSummary = useMemo(
    () =>
      cloudDrafts.find(
        (item) =>
          item.scope_key ===
          buildCloudDraftScopeKey(selectedBranchId, selectedVolumeId, chapterNumber),
      ) ?? null,
    [chapterNumber, cloudDrafts, selectedBranchId, selectedVolumeId],
  );

  const persistedChapterSummary = useMemo(
    () => chapterSummaries.find((item) => item.chapter_number === chapterNumber) ?? null,
    [chapterNumber, chapterSummaries],
  );

  const visibleFinalResult = useMemo(() => {
    if (finalResult) {
      return finalResult;
    }
    if (
      !persistedChapterSummary ||
      (persistedChapterSummary.kb_update_suggestions?.length ?? 0) === 0
    ) {
      return null;
    }
    return {
      final_draft: draftText,
      revision_notes: [],
      chapter_summary: persistedChapterSummary,
      kb_update_list: persistedChapterSummary.kb_update_suggestions,
      agent_reports: [],
      deliberation_rounds: [],
      original_draft: draftText,
      consensus_rounds: 1,
      consensus_reached: false,
      remaining_issue_count: 0,
      ready_for_publish: false,
      quality_summary: null,
      workflow_timeline: [],
    } satisfies FinalOptimizeResponse;
  }, [draftText, finalResult, persistedChapterSummary]);

  const canApplyOptimizedDraft = useMemo(() => {
    if (!finalResult) {
      return false;
    }
    return finalResult.final_draft.trim().length > 0 && finalResult.final_draft !== draftText;
  }, [draftText, finalResult]);

  // 在线状态检测
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setIsOnline(window.navigator.onLine);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // 加载本地草稿
  const loadRecoverableLocalDrafts = useCallback(async () => {
    const drafts = await listStoryRoomLocalDrafts(projectId);
    setRecoverableLocalDrafts(drafts);
  }, [projectId]);

  useEffect(() => {
    void loadRecoverableLocalDrafts();
  }, [loadRecoverableLocalDrafts]);

  // 加载云端草稿
  const loadCloudDrafts = useCallback(async () => {
    if (!isOnline) {
      return;
    }
    try {
      const data = await apiFetchWithAuth<StoryRoomCloudDraftSummary[]>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts`,
      );
      setCloudDrafts(data);
    } catch (err) {
      console.warn("[draft] Failed to fetch cloud drafts:", err);
      setCloudDrafts([]);
    }
  }, [isOnline, projectId]);

  useEffect(() => {
    if (!isOnline) {
      setCloudSyncing(false);
      return;
    }
    void loadCloudDrafts();
  }, [isOnline, loadCloudDrafts]);

  // 加载当前云端草稿
  const loadCurrentCloudDraft = useCallback(async () => {
    if (!isOnline || !currentCloudDraftSummary) {
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
      setCloudDraftSavedAt(null);
      return;
    }

    try {
      const data = await apiFetchWithAuth<StoryRoomCloudDraft | null>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts/${currentCloudDraftSummary.draft_snapshot_id}`,
      );
      if (!data) {
        setPendingCloudDraftSnapshot(null);
        setPendingCloudDraftRecoveryState(null);
        setCloudDraftSavedAt(null);
        return;
      }

      const cloudSnapshot = toLocalDraftSnapshotFromCloudDraft(data);
      const recovery = analyzeStoryRoomLocalDraftRecovery(cloudSnapshot, {
        chapterId: activeChapter?.id ?? null,
        chapterTitle: activeChapter?.title ?? "",
        draftText: activeChapter?.content ?? "",
        currentVersionNumber: activeChapter?.current_version_number ?? null,
      });

      setPendingCloudDraftSnapshot(recovery?.canRestore ? data : null);
      setPendingCloudDraftRecoveryState(recovery?.canRestore ? recovery.state : null);
      setCloudDraftSavedAt(data.updated_at);
    } catch (err) {
      console.warn("[draft] Failed to fetch pending cloud draft:", err);
      setPendingCloudDraftSnapshot(null);
      setPendingCloudDraftRecoveryState(null);
    }
  }, [
    activeChapter?.content,
    activeChapter?.current_version_number,
    activeChapter?.id,
    activeChapter?.title,
    currentCloudDraftSummary,
    isOnline,
    projectId,
  ]);

  useEffect(() => {
    if (draftDirty || scopeChapters.length === 0) {
      return;
    }
    void loadCurrentCloudDraft();
  }, [draftDirty, loadCurrentCloudDraft, scopeChapters.length]);

  // 加载当前本地草稿
  useEffect(() => {
    if (!currentLocalDraftKey) {
      return;
    }

    let cancelled = false;
    const loadLocalDraftSnapshot = async () => {
      const localDraftSnapshot = await readStoryRoomLocalDraft(currentLocalDraftKey);
      if (cancelled) {
        return;
      }

      const recovery = localDraftSnapshot
        ? analyzeStoryRoomLocalDraftRecovery(localDraftSnapshot, {
            chapterId: activeChapter?.id ?? null,
            chapterTitle: activeChapter?.title ?? "",
            draftText: activeChapter?.content ?? "",
            currentVersionNumber: activeChapter?.current_version_number ?? null,
          })
        : null;

      setPendingLocalDraftSnapshot(
        localDraftSnapshot && recovery?.canRestore ? localDraftSnapshot : null,
      );
      setPendingLocalDraftRecoveryState(
        localDraftSnapshot && recovery?.canRestore ? recovery.state : null,
      );
      setLocalDraftSavedAt(localDraftSnapshot?.updatedAt ?? null);
    };

    void loadLocalDraftSnapshot();
    return () => {
      cancelled = true;
    };
  }, [activeChapter?.content, activeChapter?.current_version_number, activeChapter?.id, activeChapter?.title, currentLocalDraftKey]);

  // 自动保存本地草稿
  useEffect(() => {
    if (!draftDirty || !currentLocalDraftKey) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void (async () => {
        if (!chapterTitle.trim() && !draftText.trim()) {
          await removeStoryRoomLocalDraft(currentLocalDraftKey);
          setRecoverableLocalDrafts((current) =>
            current.filter((item) => item.storageKey !== currentLocalDraftKey),
          );
          setLocalDraftSavedAt(null);
          return;
        }

        const snapshot: StoryRoomLocalDraftSnapshot = {
          projectId,
          branchId: selectedBranchId,
          volumeId: selectedVolumeId,
          chapterNumber,
          chapterTitle,
          draftText,
          outlineId: currentOutline?.outline_id ?? null,
          sourceChapterId: activeChapter?.id ?? null,
          sourceVersionNumber: activeChapter?.current_version_number ?? null,
          updatedAt: new Date().toISOString(),
        };
        await writeStoryRoomLocalDraft(currentLocalDraftKey, snapshot);
        
        const nextSummary = summarizeStoryRoomLocalDraft(currentLocalDraftKey, snapshot);
        if (nextSummary.chapterTitle.trim().length > 0 || nextSummary.charCount > 0) {
          setRecoverableLocalDrafts((current) => {
            const next = current.filter((item) => item.storageKey !== currentLocalDraftKey);
            next.unshift(nextSummary);
            next.sort((left, right) => {
              return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
            });
            return next;
          });
        }
        setLocalDraftSavedAt(snapshot.updatedAt);
      })();
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [
    activeChapter?.current_version_number,
    activeChapter?.id,
    chapterNumber,
    chapterTitle,
    currentLocalDraftKey,
    currentOutline?.outline_id,
    draftDirty,
    draftText,
    projectId,
    selectedBranchId,
    selectedVolumeId,
  ]);

  // 自动同步云端草稿
  useEffect(() => {
    if (
      !draftDirty ||
      !isOnline ||
      savingDraft ||
      finalizingAction !== null ||
      reviewSubmittingActionKey !== null
    ) {
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        if (!chapterTitle.trim() && !draftText.trim()) {
          return;
        }

        setCloudSyncing(true);
        try {
          const payload: StoryRoomCloudDraftUpsertRequest = {
            branch_id: selectedBranchId,
            volume_id: selectedVolumeId,
            chapter_number: chapterNumber,
            chapter_title: chapterTitle,
            draft_text: draftText,
            outline_id: currentOutline?.outline_id ?? null,
            source_chapter_id: activeChapter?.id ?? null,
            source_version_number: activeChapter?.current_version_number ?? null,
          };
          const draft = await apiFetchWithAuth<StoryRoomCloudDraft>(
            `/api/v1/projects/${projectId}/story-engine/cloud-drafts/current`,
            {
              method: "PUT",
              body: JSON.stringify(payload),
            },
          );
          if (cancelled) {
            return;
          }
          setCloudDraftSavedAt(draft.updated_at);
        } catch (err) {
          console.warn("[draft] Cloud save failed:", err);
        } finally {
          if (!cancelled) {
            setCloudSyncing(false);
          }
        }
      })();
    }, 1200);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [
    activeChapter?.current_version_number,
    activeChapter?.id,
    chapterNumber,
    chapterTitle,
    currentOutline?.outline_id,
    draftDirty,
    draftText,
    finalizingAction,
    isOnline,
    projectId,
    reviewSubmittingActionKey,
    savingDraft,
    selectedBranchId,
    selectedVolumeId,
  ]);

  // 加载章节审查状态
  useEffect(() => {
    if (!activeChapter?.id) {
      setReviewWorkspace(null);
      setChapterVersions([]);
      setLoadingChapterReview(false);
      return;
    }
    void onLoadChapterReviewState(activeChapter.id);
  }, [activeChapter?.current_version_number, activeChapter?.id, onLoadChapterReviewState]);

  // 防止未保存离开
  useEffect(() => {
    if (!draftDirty && !streamingChapter && !savingDraft) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [draftDirty, savingDraft, streamingChapter]);

  // 清除当前本地草稿
  const handleClearCurrentLocalDraft = useCallback(async () => {
    if (!currentLocalDraftKey) {
      return;
    }
    await removeStoryRoomLocalDraft(currentLocalDraftKey);
    setRecoverableLocalDrafts((current) =>
      current.filter((item) => item.storageKey !== currentLocalDraftKey),
    );
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftSavedAt(null);
    setLocalDraftRecoveredAt(null);
  }, [currentLocalDraftKey]);

  // 清除当前云端草稿
  const handleClearCurrentCloudDraft = useCallback(async () => {
    const targetDraftSnapshotId =
      currentCloudDraftSummary?.draft_snapshot_id ?? pendingCloudDraftSnapshot?.draft_snapshot_id ?? null;
    if (!isOnline || !targetDraftSnapshotId) {
      return;
    }
    try {
      await apiFetchWithAuth<void>(
        `/api/v1/projects/${projectId}/story-engine/cloud-drafts/${targetDraftSnapshotId}`,
        {
          method: "DELETE",
        },
      );
    } catch (err) {
      console.warn("[draft] Cloud draft delete failed:", err);
      return;
    }
    setCloudDrafts((current) =>
      current.filter((item) => item.draft_snapshot_id !== targetDraftSnapshotId),
    );
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftSavedAt(null);
    setCloudDraftRecoveredAt(null);
  }, [currentCloudDraftSummary?.draft_snapshot_id, isOnline, pendingCloudDraftSnapshot?.draft_snapshot_id, projectId]);

  // 恢复本地草稿
  const handleRestoreLocalDraft = useCallback(() => {
    if (!pendingLocalDraftSnapshot) {
      return;
    }
    onChapterTitleChange(pendingLocalDraftSnapshot.chapterTitle);
    onDraftTextChange(pendingLocalDraftSnapshot.draftText);
    setDraftDirty(true);
    setLocalDraftRecoveredAt(pendingLocalDraftSnapshot.updatedAt);
    setLocalDraftSavedAt(pendingLocalDraftSnapshot.updatedAt);
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setCloudDraftRecoveredAt(null);
    onSuccess("已恢复本机暂存的正文。");
  }, [onChapterTitleChange, onDraftTextChange, onSuccess, pendingLocalDraftSnapshot]);

  // 忽略本地草稿
  const handleDismissLocalDraft = useCallback(() => {
    void handleClearCurrentLocalDraft();
  }, [handleClearCurrentLocalDraft]);

  // 恢复云端草稿
  const handleRestoreCloudDraft = useCallback(() => {
    if (!pendingCloudDraftSnapshot) {
      return;
    }
    onChapterTitleChange(pendingCloudDraftSnapshot.chapter_title);
    onDraftTextChange(pendingCloudDraftSnapshot.draft_text);
    setDraftDirty(true);
    setCloudDraftRecoveredAt(pendingCloudDraftSnapshot.updated_at);
    setCloudDraftSavedAt(pendingCloudDraftSnapshot.updated_at);
    setPendingCloudDraftSnapshot(null);
    setPendingCloudDraftRecoveryState(null);
    setPendingLocalDraftSnapshot(null);
    setPendingLocalDraftRecoveryState(null);
    setLocalDraftRecoveredAt(null);
    onSuccess("已恢复这份续写稿，现在可以直接接着写。");
  }, [onChapterTitleChange, onDraftTextChange, onSuccess, pendingCloudDraftSnapshot]);

  // 忽略云端草稿
  const handleDismissCloudDraft = useCallback(() => {
    void handleClearCurrentCloudDraft();
  }, [handleClearCurrentCloudDraft]);

  // 保存草稿
  const handleSaveDraft = useCallback(async () => {
    setSavingDraft(true);
    onError("");
    onSuccess("");

    try {
      const currentOutline = outlineList.find(
        (item) => item.level === "level_3" && item.node_order === chapterNumber,
      ) ?? null;
      const outlinePayload = buildChapterOutlinePayload(currentOutline);

      if (activeChapter) {
        const payload: Record<string, unknown> = {
          title: chapterTitle.trim() || null,
          content: draftText,
          outline: outlinePayload,
          change_reason: "Saved from story room",
          create_version: true,
        };
        if (activeChapter.status === "draft" && draftText.trim().length > 0) {
          payload.status = "writing";
        }
        const updatedChapter = await updateLegacyChapter(projectId, activeChapter.id, payload);
        setDraftDirty(false);
        await handleClearCurrentLocalDraft();
        await handleClearCurrentCloudDraft();
        onSuccess(`第 ${chapterNumber} 章已保存，版本和发布状态都会按这版继续跟进。`);
      } else {
        const createdChapter = await createLegacyChapter(projectId, {
          chapter_number: chapterNumber,
          volume_id: selectedVolumeId,
          branch_id: selectedBranchId,
          title: chapterTitle.trim() || null,
          content: draftText,
          outline: outlinePayload,
          status: draftText.trim().length > 0 ? "writing" : "draft",
          change_reason: "Created from story room",
        });
        setDraftDirty(false);
        await handleClearCurrentLocalDraft();
        await handleClearCurrentCloudDraft();
        onSuccess(`第 ${chapterNumber} 章已经存成正式章节，后续修改都会留下版本记录。`);
      }

      await Promise.all([onRefreshChapterChain(), onLoadStyleControlState(false)]);
    } catch (requestError) {
      onError(buildUserFriendlyError(requestError));
    } finally {
      setSavingDraft(false);
    }
  }, [
    activeChapter,
    chapterNumber,
    chapterTitle,
    draftText,
    handleClearCurrentCloudDraft,
    handleClearCurrentLocalDraft,
    onError,
    onLoadStyleControlState,
    onRefreshChapterChain,
    onSuccess,
    outlineList,
    projectId,
    selectedBranchId,
    selectedVolumeId,
  ]);

  // 应用优化稿
  const handleApplyOptimizedDraft = useCallback(() => {
    if (!finalResult) {
      onError("当前还没有可采纳的优化稿。");
      return;
    }

    if (finalResult.final_draft === draftText) {
      onSuccess("优化稿已经在正文里了，可以直接继续微调。");
      return;
    }

    onDraftTextChange(finalResult.final_draft);
    setDraftDirty(true);
    onSuccess("优化稿已经带回正文编辑区了，确认无误后记得保存正文。");
  }, [draftText, finalResult, onDraftTextChange, onError, onSuccess]);

  return {
    // 状态
    guardResult,
    pausedStreamState,
    activeRepairInstruction,
    finalResult,
    checkingGuard,
    streamingChapter,
    streamStatus,
    optimizing,
    savingDraft,
    draftDirty,
    isOnline,
    localDraftSavedAt,
    localDraftRecoveredAt,
    pendingLocalDraftSnapshot,
    pendingLocalDraftRecoveryState,
    cloudDraftSavedAt,
    cloudDraftRecoveredAt,
    pendingCloudDraftSnapshot,
    pendingCloudDraftRecoveryState,
    cloudSyncing,
    exportingFormat,
    finalizingAction,
    reviewWorkspace,
    chapterVersions,
    loadingChapterReview,
    reviewSubmittingActionKey,
    recoverableLocalDrafts,
    cloudDrafts,
    currentLocalDraftKey,
    currentCloudDraftSummary,
    // 计算属性
    persistedChapterSummary,
    visibleFinalResult,
    canApplyOptimizedDraft,
    // 操作
    setDraftDirty,
    setGuardResult,
    setPausedStreamState,
    setFinalResult,
    setStreamStatus,
    setStreamingChapter,
    handleSaveDraft,
    handleApplyOptimizedDraft,
    handleRestoreLocalDraft,
    handleDismissLocalDraft,
    handleRestoreCloudDraft,
    handleDismissCloudDraft,
    handleClearCurrentCloudDraft,
    handleClearCurrentLocalDraft,
  };
}