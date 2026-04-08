"use client";

import type { StoryRoomStageKey } from "../types";

interface CreationPhaseProps {
  projectId: string;
  stage: StoryRoomStageKey;
}

export function CreationPhase({ projectId, stage }: CreationPhaseProps) {
  if (stage !== "draft") {
    return null;
  }
  return (
    <div className="creation-phase">
      <p>CreationPhase placeholder - 待从 page.tsx 迁移</p>
    </div>
  );
}
