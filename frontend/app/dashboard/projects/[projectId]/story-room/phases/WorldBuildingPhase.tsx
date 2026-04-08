"use client";

import type { StoryRoomStageKey } from "../types";

interface WorldBuildingPhaseProps {
  projectId: string;
  stage: StoryRoomStageKey;
}

export function WorldBuildingPhase({ projectId, stage }: WorldBuildingPhaseProps) {
  if (stage !== "world-building") {
    return null;
  }
  return (
    <div className="world-building-phase">
      <p>WorldBuildingPhase placeholder - 待从 page.tsx 迁移</p>
    </div>
  );
}
