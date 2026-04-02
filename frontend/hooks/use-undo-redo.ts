"use client";

import { useCallback, useState } from "react";
import {
  getChapterUndoRedoStatus,
  listChapterSnapshots,
  redoChapter,
  undoChapter,
  type SnapshotResponse,
  type UndoRedoStatus,
} from "@/lib/api";

interface UseUndoRedoOptions {
  chapterId: string;
  onRestore?: (content: string, snapshot: SnapshotResponse) => void;
}

export function useUndoRedo({ chapterId, onRestore }: UseUndoRedoOptions) {
  const [status, setStatus] = useState<UndoRedoStatus | null>(null);
  const [history, setHistory] = useState<SnapshotResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([
        getChapterUndoRedoStatus(chapterId),
        listChapterSnapshots(chapterId, 20),
      ]);
      setStatus(s);
      setHistory(h);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    }
  }, [chapterId]);

  const undo = useCallback(async () => {
    setLoading(true);
    try {
      const result = await undoChapter(chapterId);
      if (result.success && result.snapshot) {
        onRestore?.(result.snapshot.content, result.snapshot);
        await refresh();
      } else {
        setError(result.message ?? "Undo failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Undo error");
    } finally {
      setLoading(false);
    }
  }, [chapterId, onRestore, refresh]);

  const redo = useCallback(async () => {
    setLoading(true);
    try {
      const result = await redoChapter(chapterId);
      if (result.success && result.snapshot) {
        onRestore?.(result.snapshot.content, result.snapshot);
        await refresh();
      } else {
        setError(result.message ?? "Redo failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Redo error");
    } finally {
      setLoading(false);
    }
  }, [chapterId, onRestore, refresh]);

  return {
    status,
    history,
    loading,
    error,
    canUndo: status?.can_undo ?? false,
    canRedo: status?.can_redo ?? false,
    currentVersion: status?.current_version ?? -1,
    totalVersions: status?.total_versions ?? 0,
    undo,
    redo,
    refresh,
  };
}
