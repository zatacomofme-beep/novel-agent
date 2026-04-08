"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  startWorldBuildingSession,
  getActiveWorldBuildingSession,
  processWorldBuildingStep,
  type WorldBuildingStartResponse,
  type WorldBuildingStepResponse,
  type WorldBuildingSessionData,
} from "@/lib/api";
import { escapeHtml } from "@/lib/security";

type WorldBuildingPanelProps = {
  projectId: string;
  initialIdea?: string;
  onComplete?: () => void;
};

const STEP_TITLES: Record<number, string> = {
  1: "世界基底",
  2: "物理世界",
  3: "力量体系",
  4: "社会结构",
  5: "主角定位",
  6: "核心冲突",
  7: "世界细节",
  8: "风格偏好",
};

export function WorldBuildingPanel({ projectId, initialIdea, onComplete }: WorldBuildingPanelProps) {
  const [session, setSession] = useState<WorldBuildingStartResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [stepTitle, setStepTitle] = useState<string>("世界基底");
  const [question, setQuestion] = useState<string>("");
  const [userInput, setUserInput] = useState<string>("");
  const [modelSummary, setModelSummary] = useState<string>("");
  const [modelExpansion, setModelExpansion] = useState<string>("");
  const [isAwaitingFollowUp, setIsAwaitingFollowUp] = useState<boolean>(false);
  const [canSkip, setCanSkip] = useState<boolean>(false);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [stepHistory, setStepHistory] = useState<Array<{ step: number; title: string; summary: string }>>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        setError(null);

        const existing = await getActiveWorldBuildingSession(projectId);
        if (existing && existing.status === "in_progress") {
          const stepData = existing.session_data?.[`step_${existing.current_step}`] as { model_expansion?: string } | undefined;
          setQuestion(stepData?.model_expansion ?? STEP_TITLES[existing.current_step] ?? "请继续回答");
          setCurrentStep(existing.current_step);
          setStepTitle(STEP_TITLES[existing.current_step] ?? `步骤 ${existing.current_step}`);
          setSession({ session: existing, first_question: "", step: existing.current_step, step_title: STEP_TITLES[existing.current_step] ?? "" });
        } else {
          const result = await startWorldBuildingSession(projectId, initialIdea);
          setSession(result);
          setQuestion(result.first_question);
          setCurrentStep(result.step);
          setStepTitle(result.step_title);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "初始化失败");
      } finally {
        setLoading(false);
      }
    }

    void init();
  }, [projectId, initialIdea]);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [question, loading]);

  const handleSubmit = useCallback(async () => {
    if (!userInput.trim() || !session || loading) return;

    try {
      setLoading(true);
      setError(null);

      const result: WorldBuildingStepResponse = await processWorldBuildingStep(
        projectId,
        session.session.id,
        userInput.trim(),
      );

      if (result.model_summary) {
        setStepHistory(prev => [...prev, { step: currentStep, title: stepTitle, summary: result.model_summary }]);
      }

      setModelSummary(result.model_summary);
      setModelExpansion(result.model_expansion);
      setIsAwaitingFollowUp(result.is_awaiting_follow_up);
      setCanSkip(result.can_skip);
      setIsComplete(result.is_complete);
      setUserInput("");

      if (result.is_complete) {
        onComplete?.();
      } else {
        setCurrentStep(result.suggested_next_step);
        setStepTitle(STEP_TITLES[result.suggested_next_step] ?? `步骤 ${result.suggested_next_step}`);
        setQuestion(result.model_expansion || "请继续回答");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "处理失败");
    } finally {
      setLoading(false);
    }
  }, [userInput, session, projectId, loading, currentStep, stepTitle, onComplete]);

  const handleSkip = useCallback(async () => {
    if (!session || loading) return;

    try {
      setLoading(true);
      setError(null);

      const result: WorldBuildingStepResponse = await processWorldBuildingStep(
        projectId,
        session.session.id,
        "",
        true,
      );

      setCurrentStep(result.suggested_next_step);
      setStepTitle(STEP_TITLES[result.suggested_next_step] ?? `步骤 ${result.suggested_next_step}`);
      setQuestion(result.model_expansion || "请继续回答");
      setCanSkip(result.can_skip);
      setIsComplete(result.is_complete);
      setUserInput("");
      setModelSummary("");
      setModelExpansion("");

      if (result.is_complete) {
        onComplete?.();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "跳过失败");
    } finally {
      setLoading(false);
    }
  }, [session, projectId, loading, onComplete]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  }, [handleSubmit]);

  if (loading && !session) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-copper border-t-transparent mx-auto" />
          <p className="text-sm text-black/50">正在准备世界观引导...</p>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <section id="story-stage-world-building" className="scroll-mt-6 space-y-4">
        <div className="rounded-[24px] border border-green-200 bg-green-50 p-6 text-center">
          <p className="text-lg font-semibold text-green-700">世界观设定完成！</p>
          <p className="mt-2 text-sm text-green-600">已完成 {stepHistory.length} 个步骤的引导，可以开始生成大纲了。</p>
        </div>
      </section>
    );
  }

  return (
    <section
      id="story-stage-world-building"
      className="scroll-mt-6 space-y-4"
      data-testid="story-room-stage-world-building"
    >
      <div className="flex items-center justify-between gap-4 rounded-[24px] border border-black/10 bg-white/82 px-5 py-4 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-copper">第一步</p>
          <h2 className="mt-1 text-xl font-semibold">世界观构建</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-copper/10 px-3 py-1 text-xs font-medium text-copper">
            步骤 {currentStep}/8
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            {stepTitle}
          </span>
        </div>
      </div>

      {error && (
        <div className="rounded-[24px] border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {stepHistory.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.14em] text-black/40">已完成的步骤</p>
          {stepHistory.map(item => (
            <details key={item.step} className="group rounded-[16px] border border-black/5 bg-white/60">
              <summary className="cursor-pointer px-4 py-3 text-sm font-medium hover:bg-black/[0.02]">
                步骤{item.step}：{item.title}
              </summary>
              <div className="border-t border-black/5 px-4 py-3 text-sm leading-7 text-black/70 whitespace-pre-wrap">
                {item.summary}
              </div>
            </details>
          ))}
        </div>
      )}

      <div className="rounded-[24px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
        {(modelSummary || modelExpansion) && (
          <div className="mb-6 rounded-[16px] bg-gradient-to-br from-copper/5 to-orange-50/50 p-5">
            {modelSummary && (
              <div className="mb-4 prose prose-sm max-w-none">
                <div dangerouslySetInnerHTML={{ __html: escapeHtml(modelSummary).replace(/\n/g, '<br/>') }} />
              </div>
            )}
            {modelExpansion && (
              <div className="prose prose-sm max-w-none text-black/80">
                <div dangerouslySetInnerHTML={{ __html: escapeHtml(modelExpansion).replace(/\n/g, '<br/>') }} />
              </div>
            )}
          </div>
        )}

        {!isAwaitingFollowUp ? (
          <>
            <label htmlFor="wb-question" className="block text-base font-medium mb-3">
              {question || `步骤${currentStep}：${stepTitle}`}
            </label>
            <textarea
              ref={inputRef}
              id="wb-question"
              value={userInput}
              onChange={e => setUserInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="描述你的想法..."
              rows={4}
              disabled={loading}
              className="w-full resize-none rounded-xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 placeholder:text-black/30 focus:border-copper focus:outline-none focus:ring-2 focus:ring-copper/20 disabled:opacity-50"
            />
          </>
        ) : (
          <div className="rounded-xl bg-blue-50 p-4">
            <p className="text-sm text-blue-700">{modelExpansion}</p>
            <label htmlFor="wb-followup" className="mt-3 block text-sm font-medium">
              追问回答：
            </label>
            <textarea
              ref={inputRef}
              id="wb-followup"
              value={userInput}
              onChange={e => setUserInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="继续补充..."
              rows={3}
              disabled={loading}
              className="mt-2 w-full resize-none rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm leading-7 placeholder:text-black/30 focus:border-copper focus:outline-none focus:ring-2 focus:ring-copper/20 disabled:opacity-50"
            />
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-3">
          {canSkip && !isAwaitingFollowUp && (
            <button
              onClick={() => void handleSkip()}
              disabled={loading}
              className="rounded-full border border-black/10 bg-white px-5 py-2.5 text-sm font-medium text-black/60 hover:bg-black/[0.02] disabled:opacity-50 transition-colors"
            >
              跳过此步
            </button>
          )}
          <button
            onClick={() => void handleSubmit()}
            disabled={!userInput.trim() || loading}
            className="rounded-full bg-copper px-6 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-copper/90 disabled:opacity-50 disabled:hover:bg-copper transition-colors"
          >
            {loading ? "处理中..." : isAwaitingFollowUp ? "继续" : "提交"}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-center gap-2 py-4">
        {Array.from({ length: 8 }, (_, i) => i + 1).map(step => (
          <div
            key={step}
            className={`h-2 flex-1 max-w-8 rounded-full transition-colors ${
              step < currentStep ? 'bg-copper' :
              step === currentStep ? 'bg-copper/60 animate-pulse' :
              'bg-black/10'
            }`}
          />
        ))}
      </div>
    </section>
  );
}
