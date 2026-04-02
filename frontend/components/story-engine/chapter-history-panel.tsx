"use client";

import { useEffect, useState } from "react";
import { useUndoRedo } from "@/hooks/use-undo-redo";
import type { SnapshotResponse } from "@/lib/api";

interface ChapterHistoryPanelProps {
  chapterId: string;
  onClose: () => void;
}

export function ChapterHistoryPanel({ chapterId, onClose }: ChapterHistoryPanelProps) {
  const {
    history,
    loading,
    error,
    canUndo,
    canRedo,
    currentVersion,
    totalVersions,
    undo,
    redo,
    refresh,
  } = useUndoRedo({
    chapterId,
    onRestore: (content) => {
      console.info("Restored snapshot:", content.length, "chars");
    },
  });

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="border rounded-lg bg-white dark:bg-gray-800 max-w-lg w-full">
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h3 className="text-lg font-semibold">版本历史</h3>
          <p className="text-xs text-gray-500">
            V{currentVersion} / 共 {totalVersions} 个版本
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
        >
          ✕
        </button>
      </div>

      <div className="p-4 flex gap-2 border-b">
        <button
          onClick={undo}
          disabled={!canUndo || loading}
          className="flex-1 px-3 py-1.5 text-sm rounded border disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          ↩ Undo
        </button>
        <button
          onClick={redo}
          disabled={!canRedo || loading}
          className="flex-1 px-3 py-1.5 text-sm rounded border disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          Redo ↪
        </button>
      </div>

      {error && (
        <div className="p-3 text-sm text-red-500">{error}</div>
      )}

      <div className="max-h-80 overflow-y-auto">
        {history.length === 0 && !loading ? (
          <div className="p-6 text-center text-gray-400 text-sm">暂无历史版本</div>
        ) : (
          <ul className="divide-y">
            {history.map((snap) => (
              <SnapshotRow key={snap.id} snapshot={snap} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SnapshotRow({ snapshot }: { snapshot: SnapshotResponse }) {
  const time = new Date(snapshot.created_at).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const agentLabel: Record<string, string> = {
    writer: "Writer",
    editor: "Editor",
    critic: "Critic",
    linguistic_checker: "Linguistic",
    chaos_agent: "Chaos",
    beta_reader: "BetaReader",
  };

  return (
    <li className="p-3 hover:bg-gray-50 dark:hover:bg-gray-700">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-mono text-gray-500">V{snapshot.version_number}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300">
              {agentLabel[snapshot.trigger_agent ?? ""] ?? snapshot.trigger_agent ?? snapshot.action_type}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{time}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {snapshot.content_length} 字
            {snapshot.revision_round != null && ` · 第 ${snapshot.revision_round} 轮`}
          </p>
        </div>
      </div>
    </li>
  );
}
