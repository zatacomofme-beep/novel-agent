"use client";

import type { StoryRoomStageKey } from "../types";

interface PhaseProgressProps {
  worldBuildingCompleted: boolean;
  hasOutlineBlueprint: boolean;
  hasDraftStarted: boolean;
  activeStage: StoryRoomStageKey | null;
  onSelectStage: (stage: StoryRoomStageKey) => void;
}

interface StageConfig {
  key: StoryRoomStageKey;
  label: string;
  lockedLabel?: string;
}

const MAIN_PHASES: StageConfig[] = [
  { key: "world-building", label: "世界观" },
  { key: "outline", label: "大纲", lockedLabel: "先完成世界观" },
  { key: "draft", label: "正文", lockedLabel: "先完成大纲" },
  { key: "final", label: "终稿", lockedLabel: "先写正文" },
];

export function PhaseProgress({
  worldBuildingCompleted,
  hasOutlineBlueprint,
  hasDraftStarted,
  activeStage,
  onSelectStage,
}: PhaseProgressProps) {
  const getPhaseStatus = (key: StoryRoomStageKey): "completed" | "active" | "unlocked" | "locked" => {
    switch (key) {
      case "world-building":
        if (worldBuildingCompleted) return "completed";
        if (activeStage === "world-building") return "active";
        return "unlocked";
      case "outline":
        if (!worldBuildingCompleted) return "locked";
        if (hasOutlineBlueprint) return "completed";
        if (activeStage === "outline") return "active";
        return "unlocked";
      case "draft":
        if (!hasOutlineBlueprint) return "locked";
        if (hasDraftStarted) return "completed";
        if (activeStage === "draft") return "active";
        return "unlocked";
      case "final":
        if (!hasDraftStarted) return "locked";
        if (activeStage === "final") return "active";
        return "unlocked";
      default:
        return "locked";
    }
  };

  const handleClick = (key: StoryRoomStageKey, status: "completed" | "active" | "unlocked" | "locked") => {
    if (status !== "locked") {
      onSelectStage(key);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {MAIN_PHASES.map((phase, index) => {
        const status = getPhaseStatus(phase.key);
        const isClickable = status !== "locked";
        const isLast = index === MAIN_PHASES.length - 1;

        return (
          <div key={phase.key} className="flex items-center">
            <button
              onClick={() => handleClick(phase.key, status)}
              disabled={status === "locked"}
              className={`
                relative flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition
                ${status === "completed" ? "bg-emerald-100 text-emerald-700" : ""}
                ${status === "active" ? "bg-copper/10 text-copper border border-copper/30" : ""}
                ${status === "unlocked" ? "bg-white border border-black/10 text-black/72 hover:bg-[#f6f0e6] cursor-pointer" : ""}
                ${status === "locked" ? "bg-gray-100 text-gray-400 cursor-not-allowed" : ""}
              `}
              type="button"
            >
              <span className={`
                flex h-5 w-5 items-center justify-center rounded-full text-xs
                ${status === "completed" ? "bg-emerald-500 text-white" : ""}
                ${status === "active" ? "bg-copper text-white" : ""}
                ${status === "unlocked" ? "bg-black/10 text-black/60" : ""}
                ${status === "locked" ? "bg-gray-300 text-gray-500" : ""}
              `}>
                {status === "completed" ? "✓" : index + 1}
              </span>
              <span>{phase.label}</span>
              {status === "locked" && phase.lockedLabel && (
                <span className="ml-1 text-xs text-gray-400">🔒</span>
              )}
            </button>
            {!isLast && (
              <span className={`mx-1 ${status === "completed" ? "text-emerald-400" : "text-gray-300"}`}>›</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
