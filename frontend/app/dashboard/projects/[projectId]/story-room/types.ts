import type {
  StoryEngineWorkflowEvent,
  StoryChapterSummary,
  StoryKnowledgeSuggestion,
  StoryOutline,
  Chapter,
  TaskPlayback,
  TaskState,
} from "@/types/api";
import type {
  ProcessPlaybackStep,
  ProcessPlaybackStatus,
} from "@/components/process-playback-panel";
import type { StoryRoomLocalDraftSummary } from "@/lib/story-room-local-draft";
import type { KnowledgeTabKey } from "@/components/story-engine/knowledge-base-board";

export type StoryRoomStageKey = "outline" | "draft" | "final" | "knowledge" | "world-building";

export type PausedStreamState = {
  pausedAtParagraph: number;
  nextParagraphIndex: number;
  paragraphTotal: number;
  currentBeat: string | null;
  remainingBeats: string[];
};

export type StreamContinueOptions = {
  resumeFromParagraph?: number | null;
  repairInstruction?: string | null;
  rewriteLatestParagraph?: boolean;
};

export type DraftStudioRecoverableDraft = StoryRoomLocalDraftSummary & {
  scopeLabel: string;
  isCurrent: boolean;
};

export type StoryRoomWorkflowRun = {
  id: string;
  workflowType: string;
  stage: StoryRoomStageKey;
  label: string;
  title: string;
  summary: string;
  status: ProcessPlaybackStatus;
  progress: number | null;
  updatedAt: string;
  chapterNumber: number | null;
  steps: ProcessPlaybackStep[];
};

export type StoryBibleKnowledgeTab = Extract<
  KnowledgeTabKey,
  "locations" | "factions" | "plot_threads"
>;

export type ProjectRouteParams = {
  projectId: string;
};
