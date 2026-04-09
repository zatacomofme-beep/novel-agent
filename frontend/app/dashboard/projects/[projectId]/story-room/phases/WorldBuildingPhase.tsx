"use client";

import { WorldBuildingPanel } from "@/components/story-engine/world-building-panel";
import type { StoryRoomStageKey } from "../types";

interface WorldBuildingPhaseProps {
  projectId: string;
  stage: StoryRoomStageKey;
  initialIdea?: string;
  onComplete: () => void;
}

export function WorldBuildingPhase({
  projectId,
  stage,
  initialIdea,
  onComplete,
}: WorldBuildingPhaseProps) {
  if (stage !== "world-building") {
    return null;
  }

  return (
    <WorldBuildingPanel
      projectId={projectId}
      initialIdea={initialIdea || undefined}
      onComplete={onComplete}
    />
  );
}
