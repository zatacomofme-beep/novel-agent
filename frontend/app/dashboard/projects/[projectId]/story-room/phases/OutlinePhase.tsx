"use client";

import { OutlineWorkbench } from "@/components/story-engine/outline-workbench";
import type { OutlineStressTestResponse, StoryOutline } from "@/types/api";
import type { StoryRoomStageKey } from "../types";

interface OutlinePhaseProps {
  stage: StoryRoomStageKey;
  outlines: StoryOutline[];
  stressResult: OutlineStressTestResponse | null;
  idea: string;
  genre: string;
  tone: string;
  sourceMaterial: string;
  sourceMaterialName: string | null;
  targetChapterWords: number;
  targetTotalWords: number;
  estimatedChapterCount: number;
  stressLoading: boolean;
  savingGoalProfile: boolean;
  updatingOutlineId: string | null;
  generatingBlueprint: boolean;
  onIdeaChange: (value: string) => void;
  onGenreChange: (value: string) => void;
  onToneChange: (value: string) => void;
  onSourceMaterialChange: (value: string, name?: string | null) => void;
  onClearSourceMaterial: () => void;
  onTargetChapterWordsChange: (value: number) => void;
  onTargetTotalWordsChange: (value: number) => void;
  onSaveGoalProfile: () => void;
  onRunStressTest: () => void;
  onUpdateOutline: (outlineId: string, payload: { title: string; content: string }) => void;
  onOpenDraftStep: () => void;
}

export function OutlinePhase({
  stage,
  outlines,
  stressResult,
  idea,
  genre,
  tone,
  sourceMaterial,
  sourceMaterialName,
  targetChapterWords,
  targetTotalWords,
  estimatedChapterCount,
  stressLoading,
  savingGoalProfile,
  updatingOutlineId,
  generatingBlueprint,
  onIdeaChange,
  onGenreChange,
  onToneChange,
  onSourceMaterialChange,
  onClearSourceMaterial,
  onTargetChapterWordsChange,
  onTargetTotalWordsChange,
  onSaveGoalProfile,
  onRunStressTest,
  onUpdateOutline,
  onOpenDraftStep,
}: OutlinePhaseProps) {
  if (stage !== "outline") {
    return null;
  }

  return (
    <section
      id="story-stage-outline"
      className="scroll-mt-6 space-y-4"
      data-testid="story-room-stage-outline"
    >
      <div className="flex items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-5 py-4 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-copper">第一步</p>
          <h2 className="mt-1 text-xl font-semibold">生成三级大纲</h2>
        </div>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
          输入想法 / 上传大纲
        </span>
      </div>

      {generatingBlueprint ? (
        <div className="flex items-center justify-center gap-3 rounded-[24px] border border-copper/20 bg-[#fff7ef] p-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-copper/30 border-t-copper" />
          <p className="text-sm text-copper">正在基于你的世界观设定生成三级大纲...</p>
        </div>
      ) : null}

      <OutlineWorkbench
        outlines={outlines}
        result={stressResult}
        idea={idea}
        genre={genre}
        tone={tone}
        sourceMaterial={sourceMaterial}
        sourceMaterialName={sourceMaterialName}
        targetChapterWords={targetChapterWords}
        targetTotalWords={targetTotalWords}
        estimatedChapterCount={estimatedChapterCount}
        loading={stressLoading}
        savingGoalProfile={savingGoalProfile}
        updatingOutlineId={updatingOutlineId}
        onIdeaChange={onIdeaChange}
        onGenreChange={onGenreChange}
        onToneChange={onToneChange}
        onSourceMaterialChange={onSourceMaterialChange}
        onClearSourceMaterial={onClearSourceMaterial}
        onTargetChapterWordsChange={onTargetChapterWordsChange}
        onTargetTotalWordsChange={onTargetTotalWordsChange}
        onSaveGoalProfile={onSaveGoalProfile}
        onRunStressTest={onRunStressTest}
        onUpdateOutline={onUpdateOutline}
        onOpenDraftStep={onOpenDraftStep}
      />
    </section>
  );
}
