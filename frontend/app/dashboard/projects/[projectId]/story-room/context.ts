"use client";

import React, { createContext, useContext, useState, type ReactNode } from "react";
import type { StoryRoomStageKey } from "./types";

interface StoryRoomPhaseContextValue {
  activeStage: StoryRoomStageKey | null;
  setActiveStage: (stage: StoryRoomStageKey | null) => void;
  pendingStageScroll: StoryRoomStageKey | null;
  setPendingStageScroll: (stage: StoryRoomStageKey | null) => void;
}

const StoryRoomPhaseContext = createContext<StoryRoomPhaseContextValue | null>(null);

interface StoryRoomPhaseProviderProps {
  children: ReactNode;
  initialStage?: StoryRoomStageKey | null;
}

export function StoryRoomPhaseProvider({
  children,
  initialStage = null,
}: StoryRoomPhaseProviderProps) {
  const [activeStage, setActiveStage] = useState<StoryRoomStageKey | null>(initialStage);
  const [pendingStageScroll, setPendingStageScroll] = useState<StoryRoomStageKey | null>(null);

  return React.createElement(
    StoryRoomPhaseContext.Provider,
    { value: { activeStage, setActiveStage, pendingStageScroll, setPendingStageScroll } },
    children
  );
}

export function useStoryRoomPhase(): StoryRoomPhaseContextValue {
  const context = useContext(StoryRoomPhaseContext);
  if (!context) {
    throw new Error("useStoryRoomPhase must be used within StoryRoomPhaseProvider");
  }
  return context;
}
