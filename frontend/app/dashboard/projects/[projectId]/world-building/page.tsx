"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";
import { COPY } from "@/lib/copy";

const WORKFLOW_STEPS = [
  { key: "worldbuilding", label: "世界构建", icon: "🌍" },
  { key: "outline", label: "大纲生成", icon: "📋" },
  { key: "writing", label: "章节写作", icon: "✍️" },
];

const STEPS: Array<{
  step: number;
  title: string;
  question: string;
  optional?: boolean;
}> = [
  { step: 1, title: "世界基底",   question: "请问，这是一个什么样的世界？" },
  { step: 2, title: "物理世界",   question: "这个世界的物理法则和自然环境有什么特别之处？" },
  { step: 3, title: "力量体系",   question: "这个世界存在什么样的力量体系或超凡能力？" },
  { step: 4, title: "社会结构",   question: "这个世界的主要社会结构、势力划分和势力关系是怎样的？" },
  { step: 5, title: "主角定位",   question: "主角在这个世界中的定位是什么？" },
  { step: 6, title: "核心冲突",   question: "这个世界最核心的矛盾冲突是什么？" },
  { step: 7, title: "世界细节",   question: "这个世界还有哪些独特的风土人情或细节设定？", optional: true },
  { step: 8, title: "风格偏好",   question: "你希望这个世界的叙事风格和语言有什么偏好？", optional: true },
];

interface SessionData {
  id: string;
  project_id: string;
  current_step: number;
  last_active_step: number;
  status: string;
  completed_steps: number[];
  session_data: Record<string, any>;
}

interface StepCardData {
  step: number;
  stepTitle: string;
  modelSummary: string;
  modelExpansion: string;
  isAwaitingFollowUp: boolean;
  skipped: boolean;
}

function WorldBuildingPageContent() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;

  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<SessionData | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [userInput, setUserInput] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [displayedSteps, setDisplayedSteps] = useState<StepCardData[]>([]);
  const [visitedSteps, setVisitedSteps] = useState<number[]>([1]);
  const [isFlipping, setIsFlipping] = useState(false);
  const [streamingSummary, setStreamingSummary] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [followUpExpansion, setFollowUpExpansion] = useState("");
  const [isWaitingFollowUp, setIsWaitingFollowUp] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [allStepsDone, setAllStepsDone] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const allStepsCompleted = () => {
    if (displayedSteps.length < 8) return false;
    for (const s of STEPS) {
      const card = displayedSteps.find((d) => d.step === s.step);
      if (!card) return false;
      if (card.skipped && !s.optional) return false;
    }
    return true;
  };

  useEffect(() => {
    setAllStepsDone(allStepsCompleted());
  }, [displayedSteps]);

  const loadSession = useCallback(async () => {
    try {
      const token = getAccessToken();
      if (!token) {
        window.location.href = "/login";
        return;
      }
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/projects/${projectId}/world-building/sessions/current`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error();
      const data = await res.json();
      setSession(data.session);
      setCurrentStep(data.step);
      
      // 如果已经有完成的步骤，加载已保存的数据
      if (data.session.session_data && Object.keys(data.session.session_data).length > 0) {
        const loadedSteps: StepCardData[] = [];
        for (let stepNum = 1; stepNum <= 8; stepNum++) {
          const stepKey = `step_${stepNum}`;
          if (data.session.session_data[stepKey]) {
            const stepInfo = data.session.session_data[stepKey];
            const stepConfig = STEPS.find(s => s.step === stepNum);
            if (stepInfo.user_input && !stepInfo.skipped) {
              loadedSteps.push({
                step: stepNum,
                stepTitle: stepConfig?.title || "",
                modelSummary: stepInfo.model_summary || "",
                modelExpansion: stepInfo.model_expansion || "",
                isAwaitingFollowUp: false,
                skipped: false,
              });
            }
          }
        }
        if (loadedSteps.length > 0) {
          setDisplayedSteps(loadedSteps);
        }
      }
      
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const streamStep = useCallback(
    async (
      userInput: string,
      skipToNext: boolean = false
    ) => {
      if (!session || isStreaming) return;

      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsStreaming(true);
      setStreamError(null);
      setStreamingSummary("");
      setFollowUpExpansion("");
      setIsWaitingFollowUp(false);
      setError(null);

      const token = getAccessToken();
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/projects/${projectId}/world-building/sessions/${session.id}/step-stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ user_input: userInput, skip_to_next: skipToNext }),
            signal: controller.signal,
          }
        );

        if (!res.ok) throw new Error("Stream request failed");

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);

              if (event.event === "error") {
                setStreamError(event.message || COPY.error.unknown);
                break;
              }

              if (event.event === "chunk") {
                setStreamingSummary(event.model_summary || "");
              }

              if (event.event === "done") {
                const cardData: StepCardData = {
                  step: event.step,
                  stepTitle: event.step_title,
                  modelSummary: event.model_summary,
                  modelExpansion: event.model_expansion,
                  isAwaitingFollowUp: event.is_awaiting_follow_up,
                  skipped: skipToNext && userInput === "",
                };

                if (event.is_awaiting_follow_up) {
                  setFollowUpExpansion(event.model_expansion || "");
                  setIsWaitingFollowUp(true);
                  setStreamingSummary(event.model_summary || "");
                  setIsStreaming(false);
                  return;
                }

                setIsStreaming(false);

                if (event.is_complete) {
                  setDisplayedSteps((prev) => {
                    const filtered = prev.filter((d) => d.step !== event.step);
                    return [...filtered, cardData];
                  });
                  
                  if (event.generation_failed) {
                    setIsComplete(false);
                    setStreamError("大纲生成失败，请重试或联系管理员");
                    return;
                  }

                  setIsComplete(true);
                } else {
                  setDisplayedSteps((prev) => {
                    const filtered = prev.filter((d) => d.step !== event.step);
                    return [...filtered, cardData];
                  });
                  const nextStep = event.suggested_next_step;
                  setVisitedSteps((prev) =>
                    prev.includes(nextStep) ? prev : [...prev, nextStep]
                  );
                  setIsFlipping(true);
                  setTimeout(() => {
                    setCurrentStep(nextStep);
                    setStreamingSummary("");
                    setFollowUpExpansion("");
                    setIsWaitingFollowUp(false);
                    setUserInput("");
                    setIsFlipping(false);
                    setTimeout(() => textareaRef.current?.focus(), 100);
                  }, 300);
                }
              }
            } catch {
              // skip malformed lines
            }
          }
        }
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setStreamError(err.message || COPY.error.unknown);
      } finally {
        setIsStreaming(false);
      }
    },
    [session, projectId, isStreaming, router]
  );

  const startSession = useCallback(async () => {
    setIsStarting(true);
    setError(null);
    try {
      const token = getAccessToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/projects/${projectId}/world-building/start`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ project_id: projectId, initial_idea: "" }),
        }
      );
      if (!res.ok) throw new Error();
      const result = await res.json();
      setSession(result.session);
      setCurrentStep(result.step);
      setVisitedSteps([1]);

      setTimeout(() => {
        void streamStep("", false);
      }, 100);
    } catch {
      setError(COPY.error.unknown);
    } finally {
      setIsStarting(false);
    }
  }, [projectId, streamStep]);

  const goToStep = useCallback(
    (targetStep: number, direction: "prev" | "next") => {
      if (isFlipping || isStreaming) return;
      const stepConfig = STEPS.find((s) => s.step === targetStep);
      if (!stepConfig) return;

      if (direction === "next") {
        const currentIdx = STEPS.findIndex((s) => s.step === currentStep);
        const targetIdx = STEPS.findIndex((s) => s.step === targetStep);
        if (targetIdx !== currentIdx + 1) return;
        if (targetStep > 8) return;
      } else {
        const currentIdx = STEPS.findIndex((s) => s.step === currentStep);
        const targetIdx = STEPS.findIndex((s) => s.step === targetStep);
        if (targetIdx !== currentIdx - 1) return;
        if (targetStep < 1) return;
      }

      setIsFlipping(true);
      setTimeout(() => {
        setCurrentStep(targetStep);
        if (!visitedSteps.includes(targetStep)) {
          setVisitedSteps((prev) => [...prev, targetStep]);
        }
        setUserInput("");
        setStreamingSummary("");
        setFollowUpExpansion("");
        setIsWaitingFollowUp(false);
        setIsFlipping(false);
        setTimeout(() => textareaRef.current?.focus(), 100);
      }, 300);
    },
    [currentStep, visitedSteps, isFlipping, isStreaming]
  );

  const handleSubmit = useCallback(async () => {
    if (!session || isStreaming) return;
    if (!userInput.trim()) return;
    void streamStep(userInput, false);
  }, [session, isStreaming, userInput, streamStep]);

  const handleSkip = useCallback(async () => {
    if (!session || isStreaming) return;
    const stepConfig = STEPS.find((s) => s.step === currentStep);
    if (!stepConfig?.optional) return;
    void streamStep("", true);
  }, [session, isStreaming, currentStep, streamStep]);

  const handleFollowUpSubmit = useCallback(async () => {
    if (!session || !userInput.trim() || isStreaming) return;
    void streamStep(userInput, false);
  }, [session, isStreaming, userInput, streamStep]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="rounded-[32px] border border-black/10 bg-white/75 px-8 py-6 text-sm text-black/55 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
          {COPY.loading.thinking}
        </div>
      </div>
    );
  }

  const currentStepConfig = STEPS.find((s) => s.step === currentStep);
  const isOptional = currentStepConfig?.optional ?? false;
  const currentIdx = STEPS.findIndex((s) => s.step === currentStep);
  const canGoPrev = currentIdx > 0;
  const canGoNext = currentIdx < STEPS.length - 1;
  const hasCurrentAnswer = displayedSteps.some(
    (d) => d.step === currentStep
  );
  const currentCard = displayedSteps.find((d) => d.step === currentStep);

  if (!session) {
    return (
      <div className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-5xl">
          <button
            onClick={() => router.push("/dashboard")}
            className="mb-6 flex items-center gap-2 text-sm text-black/40 transition hover:text-black/60"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回工作台
          </button>

          <div className="mb-8">
            <p className="text-sm uppercase tracking-[0.24em] text-copper">构建世界</p>
            <h1 className="mt-3 text-4xl font-semibold">构建你的世界</h1>
            <div className="mt-5 flex items-center gap-1.5">
              <div className="w-7 h-7 rounded-full bg-copper text-paper text-xs flex items-center justify-center scale-110">
                0
              </div>
              {STEPS.map((s) => (
                <div key={s.step} className="flex items-center">
                  <div className="w-6 h-0.5 bg-black/10" />
                  <div className="w-7 h-7 rounded-full bg-[#fbfaf5] text-black/20 text-xs flex items-center justify-center">
                    {s.step}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <p className="text-xs text-black/40">初始想法</p>
              <p className="text-xs text-black/30">0/8 已完成</p>
            </div>
          </div>

          <div className="flex justify-center">
            <div className="w-full max-w-2xl">
              <div className="rounded-[36px] border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)]">
                <div className="mb-6">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">开始之前</p>
                  <p className="mt-3 text-lg text-black/72 leading-7">
                    好的故事根植于独特的世界观。
                  </p>
                  <p className="mt-2 text-sm text-black/50 leading-6">
                    接下来的 8 个问题，将帮助你一步步构建一个有血有肉的世界。从世界的基本形态，到力量体系、社会结构，再到主角的定位……每一步都是在为你的故事打地基。
                  </p>
                  <p className="mt-2 text-sm text-black/50 leading-6">
                    不需要一次性想清楚，我们可以边聊边深化。如果你暂时没有想法，也可以先跳过 optional 的步骤。
                  </p>
                </div>
                <div className="mt-5">
                  <button
                    onClick={startSession}
                    disabled={isStarting}
                    className="w-full rounded-[22px] bg-ink py-3 text-sm font-semibold text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isStarting ? "正在启动…" : "开始构建"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <button
          onClick={() => router.push("/dashboard")}
          className="mb-6 flex items-center gap-2 text-sm text-black/40 transition hover:text-black/60"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回工作台
        </button>

        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            {WORKFLOW_STEPS.map((ws, index) => {
              const isCompleted = ws.key === "worldbuilding" && allStepsDone;
              const isCurrent = ws.key === "worldbuilding";
              return (
                <div key={ws.key} className="flex items-center">
                  <div
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      isCompleted
                        ? "bg-moss text-white"
                        : isCurrent
                        ? "bg-copper/10 text-copper border border-copper/30"
                        : "bg-[#fbfaf5] text-black/30"
                    }`}
                  >
                    <span>{ws.icon}</span>
                    <span>{ws.label}</span>
                    {isCompleted && (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  {index < WORKFLOW_STEPS.length - 1 && (
                    <div className={`w-8 h-0.5 mx-1 ${isCompleted ? "bg-moss" : "bg-black/10"}`} />
                  )}
                </div>
              );
            })}
          </div>

          <p className="text-sm uppercase tracking-[0.24em] text-copper">当前阶段：世界构建</p>
          <h1 className="mt-3 text-4xl font-semibold">构建你的世界</h1>
          <div className="mt-5 flex items-center gap-1.5">
            {STEPS.map((s, index) => {
              const isCompleted = session.completed_steps.includes(s.step);
              const isCurrent = s.step === currentStep;
              const isVisited = visitedSteps.includes(s.step);
              return (
                <div key={s.step} className="flex items-center">
                  <button
                    onClick={() => {
                      const idx = STEPS.findIndex((ss) => ss.step === s.step);
                      const curIdx = currentIdx;
                      if (idx === curIdx - 1) goToStep(s.step, "prev");
                      else if (idx === curIdx + 1) goToStep(s.step, "next");
                    }}
                    disabled={
                      !isVisited ||
                      isFlipping ||
                      isStreaming ||
                      (STEPS.findIndex((ss) => ss.step === s.step) !== currentIdx - 1 &&
                        STEPS.findIndex((ss) => ss.step === s.step) !== currentIdx + 1)
                    }
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                      isCompleted || (isVisited && hasCurrentAnswer)
                        ? "bg-moss text-white cursor-pointer"
                        : isCurrent
                        ? "bg-copper text-paper scale-110"
                        : isVisited
                        ? "bg-[#fbfaf5] text-black/40 border border-black/10 cursor-pointer"
                        : "bg-[#fbfaf5] text-black/20 cursor-not-allowed"
                    } disabled:cursor-not-allowed`}
                  >
                    {isCompleted || (isVisited && hasCurrentAnswer) ? "✓" : s.step}
                  </button>
                  {index < STEPS.length - 1 && (
                    <div
                      className={`w-6 h-0.5 mx-0.5 ${
                        isCompleted || (isVisited && hasCurrentAnswer) ? "bg-moss" : "bg-black/10"
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-xs text-black/40">{currentStepConfig?.title}</p>
            <p className="text-xs text-black/30">
              {displayedSteps.length}/8 已完成
            </p>
          </div>
        </div>

        {isComplete && (
          <div className="mb-6 rounded-[24px] border border-moss/30 bg-moss/[0.06] p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-moss text-white flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-base font-semibold text-moss">世界观构建完成！</p>
                <p className="text-sm text-moss/70">接下来你可以选择下一步操作</p>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <button
                onClick={() => router.push(`/dashboard/projects/${projectId}/outline`)}
                className="flex flex-col items-center gap-2 p-4 rounded-[16px] bg-white border border-moss/20 hover:border-moss hover:bg-moss/[0.04] transition-all"
              >
                <span className="text-2xl">📋</span>
                <span className="text-sm font-medium text-ink">生成大纲</span>
                <span className="text-xs text-black/40 text-center">让AI帮你拆解三级大纲</span>
              </button>
              <button
                onClick={() => router.push(`/dashboard/projects/${projectId}/chapters`)}
                className="flex flex-col items-center gap-2 p-4 rounded-[16px] bg-white border border-black/10 hover:border-copper hover:bg-[#f8efe3]/50 transition-all"
              >
                <span className="text-2xl">✍️</span>
                <span className="text-sm font-medium text-ink">直接写作</span>
                <span className="text-xs text-black/40 text-center">基于已有设定开始写作</span>
              </button>
              <button
                onClick={() => router.push(`/dashboard/projects/${projectId}/bible`)}
                className="flex flex-col items-center gap-2 p-4 rounded-[16px] bg-white border border-black/10 hover:border-copper hover:bg-[#f8efe3]/50 transition-all"
              >
                <span className="text-2xl">📚</span>
                <span className="text-sm font-medium text-ink">设定库</span>
                <span className="text-xs text-black/40 text-center">管理和编辑世界观设定</span>
              </button>
              <button
                onClick={() => router.push(`/dashboard/projects/${projectId}/generations/characters`)}
                className="flex flex-col items-center gap-2 p-4 rounded-[16px] bg-white border border-black/10 hover:border-copper hover:bg-[#f8efe3]/50 transition-all"
              >
                <span className="text-2xl">👤</span>
                <span className="text-sm font-medium text-ink">创建角色</span>
                <span className="text-xs text-black/40 text-center">在设定中心添加角色</span>
              </button>
            </div>
          </div>
        )}

        {streamError && (
          <div className="mb-6 rounded-[24px] border border-red-200 bg-red-50 p-6">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-red-600 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="flex-1">
                <p className="text-sm font-semibold text-red-800 mb-2">大纲生成失败</p>
                <p className="text-sm text-red-700 mb-4">{streamError}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setStreamError(null);
                      void startSession();
                    }}
                    className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition"
                  >
                    重新生成大纲
                  </button>
                  <button
                    onClick={() => router.push("/dashboard")}
                    className="px-4 py-2 bg-white text-red-700 text-sm font-medium rounded-lg border border-red-300 hover:bg-red-50 transition"
                  >
                    返回工作台
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-6">
          <div className="w-80 shrink-0 space-y-4">
            <h2 className="text-xs uppercase tracking-[0.18em] text-black/40 font-medium">已完成</h2>
            {displayedSteps.length === 0 && (
              <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-5 text-sm text-black/40 text-center">
                你的回答会在这里出现
              </div>
            )}
            {displayedSteps.map((card) => {
              const config = STEPS.find((s) => s.step === card.step);
              return (
                <article
                  key={card.step}
                  className="rounded-[24px] border border-black/10 bg-white p-5 shadow-[0_8px_30px_rgba(16,20,23,0.06)]"
                >
                  <div className="mb-3 flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-moss text-white text-xs flex items-center justify-center">
                      {card.skipped ? "→" : "✓"}
                    </div>
                    <span className="text-xs text-black/50 uppercase tracking-[0.12em]">
                      {config?.title || card.stepTitle}
                      {card.skipped && (
                        <span className="ml-1 text-copper/60 normal-case tracking-normal">
                          (跳过)
                        </span>
                      )}
                    </span>
                  </div>
                  {card.skipped ? (
                    <p className="text-xs text-black/40 italic">
                      该步骤已跳过
                    </p>
                  ) : (
                    <>
                      <p className="text-sm leading-6 text-black/72 whitespace-pre-wrap">
                        {card.modelSummary}
                      </p>
                      {card.isAwaitingFollowUp && card.modelExpansion && (
                        <p className="mt-2 text-xs text-copper italic whitespace-pre-wrap">
                          {card.modelExpansion}
                        </p>
                      )}
                    </>
                  )}
                </article>
              );
            })}
          </div>

          <div
            className={`flex-1 transition-all duration-300 ${
              isFlipping
                ? "opacity-0 translate-x-6 scale-95"
                : "opacity-100 translate-x-0 scale-100"
            }`}
          >
            <div className="rounded-[36px] border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)]">
              <div className="mb-6">
                <p className="text-xs uppercase tracking-[0.18em] text-copper">
                  {currentStepConfig?.title}
                  {isOptional && (
                    <span className="ml-2 text-copper/50">（可选）</span>
                  )}
                </p>
                <p className="mt-3 text-sm text-black/62 leading-6">
                  {currentStepConfig?.question && !streamingSummary && !isWaitingFollowUp
                    ? currentStepConfig.question
                    : isWaitingFollowUp
                    ? followUpExpansion
                    : "构思中…"}
                </p>
              </div>

              {isWaitingFollowUp ? (
                <div className="rounded-[24px] border border-copper/30 bg-[#f8efe3] p-5">
                  <p className="whitespace-pre-wrap text-sm leading-6 text-black/72">
                    {followUpExpansion}
                  </p>
                </div>
              ) : null}

              {(isStreaming || streamingSummary) && !isWaitingFollowUp ? (
                <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-5">
                  <p className="whitespace-pre-wrap text-sm leading-6 text-black/72">
                    {streamingSummary}
                    <span className="inline-block w-1.5 h-4 bg-copper ml-0.5 animate-pulse align-middle" />
                  </p>
                </div>
              ) : null}

              {isWaitingFollowUp ? (
                <div className="mt-5">
                  <textarea
                    ref={textareaRef}
                    className="w-full h-32 resize-none rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm text-black/72 outline-none transition focus:border-copper"
                    placeholder="继续回答…"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                  />
                </div>
              ) : (
                <div className="mt-5">
                  <textarea
                    ref={textareaRef}
                    className="w-full h-40 resize-none rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm text-black/72 outline-none transition focus:border-copper"
                    placeholder={
                      isStreaming
                        ? "AI 正在构思中…"
                        : isWaitingFollowUp
                        ? "继续回答…"
                        : currentStepConfig?.question || "写下你的想法…"
                    }
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    disabled={isStreaming}
                  />
                </div>
              )}

              {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

              <div className="mt-5 flex gap-3">
                {isWaitingFollowUp ? (
                  <button
                    onClick={handleFollowUpSubmit}
                    disabled={!userInput.trim() || isStreaming}
                    className="flex-1 rounded-[22px] bg-ink py-3 text-sm font-semibold text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isStreaming ? "构思中…" : "继续"}
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={!userInput.trim() || isStreaming}
                    className="flex-1 rounded-[22px] bg-ink py-3 text-sm font-semibold text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isStreaming ? "构思中…" : "确认"}
                  </button>
                )}
                {isOptional && !isWaitingFollowUp && !currentCard && (
                  <button
                    onClick={handleSkip}
                    disabled={isStreaming}
                    className="rounded-[22px] border border-black/10 bg-white px-6 py-3 text-sm text-black/62 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    跳过
                  </button>
                )}
              </div>

              {!allStepsDone && !isComplete && (
                <p className="mt-3 text-xs text-black/30 text-center">
                  完成全部问题后可生成大纲
                </p>
              )}
            </div>

            <div className="mt-4 flex items-center justify-between px-2">
              <button
                onClick={() => goToStep(STEPS[currentIdx - 1].step, "prev")}
                disabled={!canGoPrev || isFlipping || isStreaming}
                className={`flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all ${
                  canGoPrev && !isFlipping && !isStreaming
                    ? "bg-white border border-black/10 text-ink hover:bg-[#f6f0e6] hover:border-copper"
                    : "bg-[#fbfaf5] text-black/20 cursor-not-allowed"
                } disabled:cursor-not-allowed`}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
                上一步
              </button>

              <div className="text-xs text-black/30">
                {currentIdx + 1} / {STEPS.length}
              </div>

              <button
                onClick={() => goToStep(STEPS[currentIdx + 1].step, "next")}
                disabled={!canGoNext || isFlipping || isStreaming}
                className={`flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all ${
                  canGoNext && !isFlipping && !isStreaming
                    ? "bg-ink text-paper hover:bg-copper"
                    : "bg-[#fbfaf5] text-black/20 cursor-not-allowed"
                } disabled:cursor-not-allowed`}
              >
                下一步
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>
            </div>

            {canGoNext && (
              <p className="mt-1 text-xs text-black/20 text-center px-2">
                可直接跳到下一步回答
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorldBuildingPage() {
  return <WorldBuildingPageContent />;
}
