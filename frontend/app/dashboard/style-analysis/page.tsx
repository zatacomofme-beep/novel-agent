"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiFetchWithAuth } from "@/lib/api";
import { loadAuthSession } from "@/lib/auth";
import { useToast } from "@/components/toast-provider";
import type { User, StylePresetAsset } from "@/types/api";

interface StyleAnalysisResult {
  writing_style: string;
  tone_and_mood: string;
  sentence_structure: string;
  vocabulary_and_expression: string;
  pacing_and_rhythm: string;
  emotional_depth: string;
  dialogue_style: string;
  narrative_perspective: string;
  tension_and_conflict: string;
  genre_characteristics: string;
  strengths: string[];
  weaknesses: string[];
  recommended_style_tags: string[];
}

function inferProseStyle(sentenceStructure: string, vocabulary: string): string {
  const text = `${sentenceStructure} ${vocabulary}`.toLowerCase();
  if (text.includes("短句") || text.includes("简洁")) return "简洁干脆";
  if (text.includes("长句") || text.includes("华丽")) return "细腻华丽";
  return "均衡";
}

function inferNarrativeMode(perspective: string): string {
  const text = perspective.toLowerCase();
  if (text.includes("第一人称")) return "first_person";
  if (text.includes("第三人称")) return "third_person";
  if (text.includes("全知")) return "omniscient";
  return "close_third";
}

function inferPacing(pacing: string): string {
  const text = pacing.toLowerCase();
  if (text.includes("快")) return "fast";
  if (text.includes("慢")) return "slow";
  return "balanced";
}

function inferDialogue(dialogue: string): string {
  const text = dialogue.toLowerCase();
  if (text.includes("多")) return "high";
  if (text.includes("少")) return "low";
  return "balanced";
}

function inferTension(tension: string): string {
  const text = tension.toLowerCase();
  if (text.includes("强")) return "high";
  if (text.includes("弱")) return "low";
  return "balanced";
}

function inferSensory(emotionalDepth: string): string {
  const text = emotionalDepth.toLowerCase();
  if (text.includes("强") || text.includes("深")) return "intense";
  if (text.includes("弱") || text.includes("淡")) return "subtle";
  return "focused";
}

function StyleAnalysisContent() {
  const searchParams = useSearchParams();
  const returnProjectId = searchParams.get("projectId");
  const toast = useToast();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"text" | "image">("text");
  const [textContent, setTextContent] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<StyleAnalysisResult | null>(null);
  const [saveTemplateName, setSaveTemplateName] = useState("");
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const session = loadAuthSession();
    if (session) {
      setCurrentUser(session.user);
    }
  }, []);

  function handleImageSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        toast.error("文件类型错误", "请选择图片文件");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error("文件过大", "图片大小不能超过10MB");
        return;
      }
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  }

  async function handleAnalyze() {
    if (mode === "text" && textContent.trim().length < 100) {
      toast.error("内容不足", "文本内容至少需要100个字");
      return;
    }
    if (mode === "image" && !imageFile) {
      toast.error("请选择图片", "需要上传一张图片才能分析");
      return;
    }

    setAnalyzing(true);

    try {
      let result: StyleAnalysisResult;
      if (mode === "text") {
        const formData = new FormData();
        formData.append("text", textContent.trim());
        const response = await apiFetchWithAuth<StyleAnalysisResult>(
          "/api/v1/style-analysis/analyze-text",
          { method: "POST", body: formData }
        );
        result = response;
      } else {
        const formData = new FormData();
        if (imageFile) {
          formData.append("file", imageFile);
        }
        const response = await apiFetchWithAuth<StyleAnalysisResult>(
          "/api/v1/style-analysis/analyze-image",
          { method: "POST", body: formData }
        );
        result = response;
      }
      setAnalysisResult(result);
      setSaveTemplateName("");
      toast.success("分析完成", "可以查看分析结果或保存为模板");
    } catch (err) {
      toast.error("分析失败", err instanceof Error ? err.message : "请重试");
      setAnalysisResult(null);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSaveAsTemplate() {
    if (!analysisResult || !saveTemplateName.trim()) {
      toast.error("保存失败", "请输入模板名称");
      return;
    }

    setSaving(true);

    try {
      const payload = {
        name: saveTemplateName.trim(),
        style_data: analysisResult,
      };

      await apiFetchWithAuth<StylePresetAsset>(
        "/api/v1/style-analysis/save-template",
        { method: "POST", body: JSON.stringify(payload) }
      );

      toast.success("保存成功", "可在风格中心查看");
      setSaveTemplateName("");
    } catch (err) {
      toast.error("保存失败", err instanceof Error ? err.message : "请重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleApplyToStyleCenter() {
    if (!analysisResult) {
      return;
    }

    setApplying(true);

    try {
      const proseStyle = inferProseStyle(
        analysisResult.sentence_structure,
        analysisResult.vocabulary_and_expression
      );
      const narrativeMode = inferNarrativeMode(analysisResult.narrative_perspective);
      const pacing = inferPacing(analysisResult.pacing_and_rhythm);
      const dialogue = inferDialogue(analysisResult.dialogue_style);
      const tension = inferTension(analysisResult.tension_and_conflict);
      const sensory = inferSensory(analysisResult.emotional_depth);

      await apiFetchWithAuth("/api/v1/profile/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          prose_style: proseStyle,
          narrative_mode: narrativeMode,
          pacing_preference: pacing,
          dialogue_preference: dialogue,
          tension_preference: tension,
          sensory_density: sensory,
          favored_elements: analysisResult.recommended_style_tags.slice(0, 5),
          banned_patterns: [],
          custom_style_notes: `【AI分析】${analysisResult.writing_style}\n${analysisResult.genre_characteristics}`,
        }),
      });

      toast.success("应用成功", "已更新风格中心的写作偏好");
    } catch (err) {
      toast.error("应用失败", err instanceof Error ? err.message : "请重试");
    } finally {
      setApplying(false);
    }
  }

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="text-sm uppercase tracking-[0.24em] text-copper">风格分析</p>
          <h1 className="mt-3 text-3xl font-semibold">请先登录</h1>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper"
              href="/login"
            >
              去登录
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <section className="rounded-[36px] border border-black/10 bg-white/78 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-copper">风格分析</p>
              <h1 className="mt-3 text-4xl font-semibold">AI 文风分析</h1>
              <p className="mt-2 text-sm text-black/60">
                上传文本或图片，AI 分析行文风格、爽点逻辑、人物刻画等特征
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium transition hover:bg-[#f6f0e6]"
                href="/dashboard"
              >
                回书架
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium transition hover:bg-[#f6f0e6]"
                href="/dashboard/preferences"
              >
                风格中心
              </Link>
              {returnProjectId ? (
                <Link
                  className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper transition hover:bg-copper"
                  href={`/dashboard/projects/${returnProjectId}/story-room`}
                >
                  回故事工作台
                </Link>
              ) : null}
            </div>
          </div>
        </section>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {success}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-2">
          <section className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <div className="mb-5 flex gap-2">
              <button
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  mode === "text"
                    ? "bg-ink text-white"
                    : "border border-black/10 bg-[#fbfaf5] text-black/68 hover:bg-[#f6f0e6]"
                }`}
                onClick={() => { setMode("text"); setError(null); setAnalysisResult(null); }}
              >
                文本分析
              </button>
              <button
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  mode === "image"
                    ? "bg-ink text-white"
                    : "border border-black/10 bg-[#fbfaf5] text-black/68 hover:bg-[#f6f0e6]"
                }`}
                onClick={() => { setMode("image"); setError(null); setAnalysisResult(null); }}
              >
                图片分析
              </button>
            </div>

            {mode === "text" ? (
              <div className="grid gap-4">
                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.16em] text-copper">
                    粘贴文本 <span className="text-black/40">(5000字以内效果最佳)</span>
                  </p>
                  <textarea
                    className="min-h-[280px] w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none resize-none"
                    placeholder="在这里粘贴你想要分析的文本内容..."
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    maxLength={30000}
                  />
                  <p className="mt-1 text-right text-xs text-black/40">
                    {textContent.length} / 30000
                  </p>
                </div>
              </div>
            ) : (
              <div className="grid gap-4">
                <div>
                  <p className="mb-2 text-xs uppercase tracking-[0.16em] text-copper">
                    上传图片 <span className="text-black/40">(支持截图、照片等)</span>
                  </p>
                  <label className="flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-[22px] border-2 border-dashed border-black/10 bg-[#fbfaf5] transition hover:border-copper/50 hover:bg-[#f6f0e6]/30">
                    {imagePreview ? (
                      <div className="relative w-full p-4">
                        <img
                          src={imagePreview}
                          alt="Preview"
                          className="max-h-[260px] w-full object-contain"
                        />
                        <button
                          className="absolute right-6 top-6 rounded-full border border-black/10 bg-white/80 px-3 py-1 text-xs backdrop-blur hover:bg-white"
                          onClick={(e) => {
                            e.preventDefault();
                            setImageFile(null);
                            setImagePreview(null);
                          }}
                        >
                          移除
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3 p-8">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full border border-black/10 bg-white">
                          <svg className="h-8 w-8 text-black/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                        <p className="text-sm text-black/60">点击选择图片</p>
                        <p className="text-xs text-black/40">或拖拽图片到这里</p>
                      </div>
                    )}
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleImageSelect}
                    />
                  </label>
                </div>
              </div>
            )}

            <button
              className="mt-5 w-full rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={analyzing}
              onClick={handleAnalyze}
            >
              {analyzing ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  分析中...
                </span>
              ) : "开始分析"}
            </button>
          </section>

          <section className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <p className="text-xs uppercase tracking-[0.2em] text-copper">分析结果</p>

            {analysisResult ? (
              <div className="mt-4 grid gap-4">
                <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-copper">文风总体</p>
                  <p className="mt-2 text-sm leading-7 text-black/75">{analysisResult.writing_style}</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">语气与情绪</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.tone_and_mood}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">句式结构</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.sentence_structure}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">词汇与表达</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.vocabulary_and_expression}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">节奏与韵律</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.pacing_and_rhythm}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">情感深度</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.emotional_depth}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">对话风格</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.dialogue_style}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">叙事视角</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.narrative_perspective}</p>
                  </div>
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">张力与冲突</p>
                    <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.tension_and_conflict}</p>
                  </div>
                </div>

                <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                  <p className="text-xs text-copper">类型特征</p>
                  <p className="mt-1 text-xs leading-6 text-black/70">{analysisResult.genre_characteristics}</p>
                </div>

                {analysisResult.strengths.length > 0 && (
                  <div className="rounded-[18px] border border-emerald-200/50 bg-emerald-50/50 p-3">
                    <p className="text-xs text-emerald-700">优点</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {analysisResult.strengths.map((item, i) => (
                        <span key={i} className="rounded-full border border-emerald-200 bg-white px-2.5 py-1 text-xs text-emerald-700">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisResult.weaknesses.length > 0 && (
                  <div className="rounded-[18px] border border-amber-200/50 bg-amber-50/50 p-3">
                    <p className="text-xs text-amber-700">待优化</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {analysisResult.weaknesses.map((item, i) => (
                        <span key={i} className="rounded-full border border-amber-200 bg-white px-2.5 py-1 text-xs text-amber-700">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisResult.recommended_style_tags.length > 0 && (
                  <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-3">
                    <p className="text-xs text-copper">推荐风格标签</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {analysisResult.recommended_style_tags.map((tag, i) => (
                        <span key={i} className="rounded-full border border-copper/20 bg-[#f6ede3] px-2.5 py-1 text-xs text-copper">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-4 rounded-[22px] border border-black/10 bg-[#f6f0e6] p-4">
                  <p className="mb-3 text-xs uppercase tracking-[0.12em] text-copper">保存为风格模板</p>
                  <div className="flex gap-2">
                    <input
                      className="flex-1 rounded-full border border-black/10 bg-white px-4 py-2 text-sm outline-none"
                      placeholder="输入模板名称..."
                      value={saveTemplateName}
                      onChange={(e) => setSaveTemplateName(e.target.value)}
                    />
                    <button
                      className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
                      disabled={saving || !saveTemplateName.trim()}
                      onClick={handleSaveAsTemplate}
                    >
                      {saving ? "保存中..." : "保存"}
                    </button>
                  </div>
                </div>

                <button
                  className="mt-3 w-full rounded-full border border-copper/40 bg-copper/10 px-4 py-3 text-sm font-semibold text-copper transition hover:bg-copper/20 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={applying || !analysisResult}
                  onClick={handleApplyToStyleCenter}
                >
                  {applying ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      应用中...
                    </span>
                  ) : "→ 一键应用到风格中心"}
                </button>
                <p className="mt-2 text-center text-xs text-black/50">
                  分析结果将自动转换为写作偏好设置
                </p>
              </div>
            ) : (
              <div className="flex min-h-[400px] flex-col items-center justify-center text-center">
                <div className="flex h-20 w-20 items-center justify-center rounded-full border border-black/10 bg-[#fbfaf5]">
                  <svg className="h-10 w-10 text-black/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="mt-4 text-sm text-black/50">分析结果将显示在这里</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

export default function StyleAnalysisPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center px-6 py-12">
          <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
            <p className="text-sm uppercase tracking-[0.24em] text-copper">风格分析</p>
            <h1 className="mt-3 text-3xl font-semibold">正在装载...</h1>
          </div>
        </main>
      }
    >
      <StyleAnalysisContent />
    </Suspense>
  );
}
