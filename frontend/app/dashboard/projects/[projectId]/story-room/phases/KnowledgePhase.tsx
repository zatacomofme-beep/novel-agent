"use client";

import {
  KnowledgeBaseBoard,
  type KnowledgeTabKey,
  type KnowledgeSuggestionKind,
} from "@/components/story-engine/knowledge-base-board";
import type {
  StoryBible,
  StoryEngineWorkspace,
  StoryBibleVersion,
  StoryBiblePendingChange,
  StoryImportTemplate,
  StorySearchResult,
  TaskEvent,
  TaskState,
} from "@/types/api";
import type { StoryRoomStageKey } from "../types";

interface KnowledgePhaseProps {
  stage: StoryRoomStageKey;
  workspace: StoryEngineWorkspace | null;
  storyBible: StoryBible | null;
  activeTab: KnowledgeTabKey;
  highlightedItemId: string | null;
  editingId: string | null;
  formState: Record<string, string>;
  saving: boolean;
  importing: boolean;
  searchQuery: string;
  searchResults: StorySearchResult[];
  importTemplates: StoryImportTemplate[];
  selectedTemplateKey: string;
  importPayloadText: string;
  replaceSections: string[];
  generationLoadingKind: KnowledgeSuggestionKind | null;
  generationTask: TaskState | null;
  generationTaskEvents: TaskEvent[];
  acceptingCandidateIndex: number | null;
  storyBibleVersions: StoryBibleVersion[];
  storyBiblePendingChanges: StoryBiblePendingChange[];
  loadingGovernance: boolean;
  governanceActionKey: string | null;
  onTabChange: (tab: KnowledgeTabKey) => void;
  onFieldChange: (field: string, value: string) => void;
  onSearchQueryChange: (query: string) => void;
  onImportTemplateChange: (value: string) => void;
  onImportPayloadChange: (text: string) => void;
  onToggleReplaceSection: (section: string) => void;
  onGenerateSuggestion: (kind: KnowledgeSuggestionKind) => void;
  onAcceptSuggestion: (candidateIndex: number) => void;
  onSearch: () => void;
  onSubmit: () => void;
  onSubmitImport: () => void;
  onStartEdit: (tab: KnowledgeTabKey, item: Record<string, unknown>) => void;
  onDelete: (tab: KnowledgeTabKey, id: string) => void;
  onJumpToRelatedChapter: (tab: KnowledgeTabKey, item: Record<string, unknown>) => void;
  onLocateSearchResult: (result: StorySearchResult) => void;
  onCancelEdit: () => void;
  onApprovePendingChange: (changeId: string) => void;
  onRejectPendingChange: (changeId: string) => void;
  onRollbackVersion: (versionId: string, versionNumber: number) => void;
}

export function KnowledgePhase({
  stage,
  storyBiblePendingChanges,
  ...boardProps
}: KnowledgePhaseProps) {
  if (stage !== "knowledge") {
    return null;
  }

  return (
    <section id="story-stage-knowledge" className="scroll-mt-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-4 py-3 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            第四步
          </span>
          <h2 className="text-lg font-semibold">设定</h2>
        </div>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
          待确认 {storyBiblePendingChanges.length} 条
        </span>
      </div>

      <KnowledgeBaseBoard
        {...boardProps}
        storyBiblePendingChanges={storyBiblePendingChanges}
      />
    </section>
  );
}
