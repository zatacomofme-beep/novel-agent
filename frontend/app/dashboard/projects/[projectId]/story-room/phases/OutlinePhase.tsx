"use client";

import type { StoryRoomStageKey } from "../types";

interface OutlinePhaseProps {
  projectId: string;
  stage: StoryRoomStageKey;
}

export function OutlinePhase({ projectId, stage }: OutlinePhaseProps) {
  if (stage !== "outline") {
    return null;
  }
  return (
    <div className="outline-phase">
      <p>OutlinePhase placeholder - 待从 page.tsx 迁移</p>
    </div>
  );
}
