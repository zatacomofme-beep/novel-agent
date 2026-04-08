"use client";

import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { StoryRoomStageKey } from "../types";

interface StoryRoomCoreState {
  projectId: string;
  workspace: Record<string, unknown> | null;
  projectStructure: Record<string, unknown> | null;
  selectedBranchId: string | null;
  selectedVolumeId: string | null;
  chapters: Array<Record<string, unknown>>;
  activeStage: StoryRoomStageKey | null;
  pendingStageScroll: StoryRoomStageKey | null;
}

interface StoryRoomCoreValue extends StoryRoomCoreState {
  setWorkspace: (workspace: Record<string, unknown> | null) => void;
  setProjectStructure: (structure: Record<string, unknown> | null) => void;
  setSelectedBranchId: (id: string | null) => void;
  setSelectedVolumeId: (id: string | null) => void;
  setChapters: (chapters: Array<Record<string, unknown>>) => void;
  setActiveStage: (stage: StoryRoomStageKey | null) => void;
  setPendingStageScroll: (stage: StoryRoomStageKey | null) => void;
}

const StoryRoomCoreContext = createContext<StoryRoomCoreValue | null>(null);

interface StoryRoomProviderProps {
  children: ReactNode;
  projectId: string;
}

export function StoryRoomProvider({ children, projectId }: StoryRoomProviderProps) {
  const [workspace, setWorkspace] = useState<Record<string, unknown> | null>(null);
  const [projectStructure, setProjectStructure] = useState<Record<string, unknown> | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [selectedVolumeId, setSelectedVolumeId] = useState<string | null>(null);
  const [chapters, setChapters] = useState<Array<Record<string, unknown>>>([]);
  const [activeStage, setActiveStage] = useState<StoryRoomStageKey | null>(null);
  const [pendingStageScroll, setPendingStageScroll] = useState<StoryRoomStageKey | null>(null);

  const value: StoryRoomCoreValue = {
    projectId,
    workspace,
    projectStructure,
    selectedBranchId,
    selectedVolumeId,
    chapters,
    activeStage,
    pendingStageScroll,
    setWorkspace,
    setProjectStructure,
    setSelectedBranchId,
    setSelectedVolumeId,
    setChapters,
    setActiveStage,
    setPendingStageScroll,
  };

  return React.createElement(StoryRoomCoreContext.Provider, { value }, children);
}

export function useStoryRoom(): StoryRoomCoreValue {
  const context = useContext(StoryRoomCoreContext);
  if (!context) {
    throw new Error("useStoryRoom must be used within StoryRoomProvider");
  }
  return context;
}
