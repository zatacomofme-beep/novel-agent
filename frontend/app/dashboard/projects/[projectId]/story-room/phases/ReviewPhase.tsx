"use client";

import type { StoryRoomStageKey } from "../types";

interface ReviewPhaseProps {
  projectId: string;
  stage: StoryRoomStageKey;
}

export function ReviewPhase({ projectId, stage }: ReviewPhaseProps) {
  if (stage !== "final") {
    return null;
  }
  return (
    <div className="review-phase">
      <p>ReviewPhase placeholder - 待从 page.tsx 迁移</p>
    </div>
  );
}
