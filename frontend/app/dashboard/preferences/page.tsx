"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { loadAuthSession } from "@/lib/auth";
import type { StyleTemplate, User, UserPreferenceProfile } from "@/types/api";

const proseStyleOptions = [
  { value: "precise", label: "精确克制" },
  { value: "lyrical", label: "抒情流动" },
  { value: "sharp", label: "冷峻锋利" },
];

const narrativeModeOptions = [
  { value: "close_third", label: "贴身第三人称" },
  { value: "omniscient", label: "多点俯瞰" },
  { value: "first_person", label: "第一人称" },
];

const pacingOptions = [
  { value: "fast", label: "快推进" },
  { value: "balanced", label: "均衡推进" },
  { value: "slow_burn", label: "慢燃积压" },
];

const dialogueOptions = [
  { value: "dialogue_forward", label: "对话驱动" },
  { value: "balanced", label: "平衡" },
  { value: "narration_heavy", label: "叙述主导" },
];

const tensionOptions = [
  { value: "restrained", label: "克制蓄压" },
  { value: "balanced", label: "张弛平衡" },
  { value: "high_tension", label: "高压逼近" },
];

const sensoryOptions = [
  { value: "minimal", label: "稀疏点染" },
  { value: "focused", label: "重点锚点" },
  { value: "immersive", label: "沉浸细节" },
];

const learningFieldLabels: Record<string, string> = {
  prose_style: "文风",
  narrative_mode: "视角",
  pacing_preference: "节奏",
  dialogue_preference: "对话比例",
  tension_preference: "张力",
  sensory_density: "感官密度",
};

const observationSourceLabels: Record<string, string> = {
  chapter_create: "新建章节",
  manual_update: "手动保存",
  rollback: "版本回滚",
};

const preferenceValueLabels: Record<string, string> = {
  precise: "精确克制",
  lyrical: "抒情流动",
  sharp: "冷峻锋利",
  close_third: "贴身第三人称",
  omniscient: "多点俯瞰",
  first_person: "第一人称",
  fast: "快推进",
  balanced: "平衡",
  slow_burn: "慢燃积压",
  dialogue_forward: "对话驱动",
  narration_heavy: "叙述主导",
  restrained: "克制蓄压",
  high_tension: "高压逼近",
  minimal: "稀疏点染",
  focused: "重点锚点",
  immersive: "沉浸细节",
};

function toTextareaValue(items: string[]): string {
  return items.join("\n");
}

function fromTextareaValue(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function PreferencesPage() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserPreferenceProfile | null>(null);
  const [templates, setTemplates] = useState<StyleTemplate[]>([]);
  const [proseStyle, setProseStyle] = useState("precise");
  const [narrativeMode, setNarrativeMode] = useState("close_third");
  const [pacingPreference, setPacingPreference] = useState("balanced");
  const [dialoguePreference, setDialoguePreference] = useState("balanced");
  const [tensionPreference, setTensionPreference] = useState("balanced");
  const [sensoryDensity, setSensoryDensity] = useState("focused");
  const [favoredElementsText, setFavoredElementsText] = useState("");
  const [bannedPatternsText, setBannedPatternsText] = useState("");
  const [customStyleNotes, setCustomStyleNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [applyingTemplateKey, setApplyingTemplateKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const session = loadAuthSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setCurrentUser(session.user);
    void loadPageData();
  }, []);

  function syncFormFromProfile(data: UserPreferenceProfile) {
    setProfile(data);
    setProseStyle(data.prose_style);
    setNarrativeMode(data.narrative_mode);
    setPacingPreference(data.pacing_preference);
    setDialoguePreference(data.dialogue_preference);
    setTensionPreference(data.tension_preference);
    setSensoryDensity(data.sensory_density);
    setFavoredElementsText(toTextareaValue(data.favored_elements));
    setBannedPatternsText(toTextareaValue(data.banned_patterns));
    setCustomStyleNotes(data.custom_style_notes ?? "");
  }

  async function loadPageData() {
    setLoading(true);
    setError(null);
    try {
      const [profileData, templateData] = await Promise.all([
        apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences"),
        apiFetchWithAuth<StyleTemplate[]>("/api/v1/profile/style-templates"),
      ]);
      syncFormFromProfile(profileData);
      setTemplates(templateData);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load preference profile.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          prose_style: proseStyle,
          narrative_mode: narrativeMode,
          pacing_preference: pacingPreference,
          dialogue_preference: dialoguePreference,
          tension_preference: tensionPreference,
          sensory_density: sensoryDensity,
          favored_elements: fromTextareaValue(favoredElementsText),
          banned_patterns: fromTextareaValue(bannedPatternsText),
          custom_style_notes: customStyleNotes.trim() || null,
        }),
      });
      syncFormFromProfile(data);
      setSuccess("风格偏好已保存，后续生成任务会直接读取这些配置。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to save preference profile.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function refreshTemplates() {
    const data = await apiFetchWithAuth<StyleTemplate[]>("/api/v1/profile/style-templates");
    setTemplates(data);
  }

  async function handleApplyTemplate(templateKey: string, mode: "replace" | "fill_defaults") {
    setApplyingTemplateKey(`${templateKey}:${mode}`);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<UserPreferenceProfile>(
        `/api/v1/profile/style-templates/${templateKey}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ mode }),
        },
      );
      syncFormFromProfile(data);
      await refreshTemplates();
      setSuccess(
        mode === "replace"
          ? "模板已覆盖应用到当前偏好。"
          : "模板已按默认补齐模式写入当前偏好。",
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to apply style template.",
      );
    } finally {
      setApplyingTemplateKey(null);
    }
  }

  async function handleClearTemplate() {
    setApplyingTemplateKey("clear");
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/style-templates/active", {
        method: "DELETE",
      });
      syncFormFromProfile(data);
      await refreshTemplates();
      setSuccess("已取消当前激活模板标记，现有偏好字段保持不变。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to clear active template.",
      );
    } finally {
      setApplyingTemplateKey(null);
    }
  }

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="text-sm uppercase tracking-[0.24em] text-copper">
            Preferences
          </p>
          <h1 className="mt-3 text-3xl font-semibold">尚未登录</h1>
          <p className="mt-4 text-sm leading-7 text-black/65">
            风格偏好属于用户级配置，登录后才能编辑。
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper"
              href="/login"
            >
              去登录
            </Link>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              href="/dashboard"
            >
              返回工作台
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <section className="rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Style Preferences
              </p>
              <h1 className="mt-3 text-4xl font-semibold">风格偏好与写作约束</h1>
              <p className="mt-3 text-sm leading-7 text-black/65">
                显式配置会直接进入 planner、writer、editor 的生成输入；手动保存与回滚形成的稳定信号也会作为隐式学习约束参与后续生成。
              </p>
            </div>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
              href="/dashboard"
            >
              返回工作台
            </Link>
          </div>
        </section>

        <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold">风格模板库</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                模板是可复用的偏好预设。`覆盖应用` 会整套替换当前风格字段，`只补默认` 只填系统默认值和空白项。
              </p>
            </div>
            {profile?.active_template ? (
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleClearTemplate()}
                disabled={applyingTemplateKey === "clear"}
              >
                {applyingTemplateKey === "clear" ? "处理中..." : "取消模板标记"}
              </button>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-2">
            {templates.map((template) => (
              <article
                key={template.key}
                className="rounded-3xl border border-black/10 bg-white/80 p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold">{template.name}</h3>
                      <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                        {template.category}
                      </span>
                      {template.is_active ? (
                        <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                          当前激活
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-7 text-black/70">
                      {template.tagline}
                    </p>
                    <p className="mt-2 text-sm leading-7 text-black/55">
                      {template.description}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {template.recommended_for.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper"
                    >
                      {item}
                    </span>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap gap-2 text-xs text-black/60">
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    文风 {preferenceValueLabels[template.prose_style] ?? template.prose_style}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    视角 {preferenceValueLabels[template.narrative_mode] ?? template.narrative_mode}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    节奏 {preferenceValueLabels[template.pacing_preference] ?? template.pacing_preference}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    对话 {preferenceValueLabels[template.dialogue_preference] ?? template.dialogue_preference}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    张力 {preferenceValueLabels[template.tension_preference] ?? template.tension_preference}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                    感官 {preferenceValueLabels[template.sensory_density] ?? template.sensory_density}
                  </span>
                </div>

                {template.favored_elements.length > 0 ? (
                  <p className="mt-4 text-sm leading-7 text-black/65">
                    重点元素：{template.favored_elements.join(" / ")}
                  </p>
                ) : null}

                {template.custom_style_notes ? (
                  <p className="mt-2 text-sm leading-7 text-black/55">
                    备注：{template.custom_style_notes}
                  </p>
                ) : null}

                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onClick={() => void handleApplyTemplate(template.key, "replace")}
                    disabled={Boolean(applyingTemplateKey)}
                  >
                    {applyingTemplateKey === `${template.key}:replace` ? "应用中..." : "覆盖应用"}
                  </button>
                  <button
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onClick={() => void handleApplyTemplate(template.key, "fill_defaults")}
                    disabled={Boolean(applyingTemplateKey)}
                  >
                    {applyingTemplateKey === `${template.key}:fill_defaults` ? "应用中..." : "只补默认"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            {loading ? (
              <p className="text-sm text-black/60">加载偏好配置中...</p>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm">
                    文风
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={proseStyle}
                      onChange={(event) => setProseStyle(event.target.value)}
                    >
                      {proseStyleOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    叙事视角
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={narrativeMode}
                      onChange={(event) => setNarrativeMode(event.target.value)}
                    >
                      {narrativeModeOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    节奏
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={pacingPreference}
                      onChange={(event) => setPacingPreference(event.target.value)}
                    >
                      {pacingOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    对话比例
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={dialoguePreference}
                      onChange={(event) => setDialoguePreference(event.target.value)}
                    >
                      {dialogueOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    张力
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={tensionPreference}
                      onChange={(event) => setTensionPreference(event.target.value)}
                    >
                      {tensionOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    感官密度
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={sensoryDensity}
                      onChange={(event) => setSensoryDensity(event.target.value)}
                    >
                      {sensoryOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="mt-6 flex flex-col gap-2 text-sm">
                  偏爱元素
                  <textarea
                    className="min-h-[120px] rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
                    value={favoredElementsText}
                    onChange={(event) => setFavoredElementsText(event.target.value)}
                    placeholder={"每行一个，例如：\n潜台词\n动作链\n身体感"}
                  />
                </label>

                <label className="mt-6 flex flex-col gap-2 text-sm">
                  禁用表达或套路
                  <textarea
                    className="min-h-[120px] rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
                    value={bannedPatternsText}
                    onChange={(event) => setBannedPatternsText(event.target.value)}
                    placeholder={"每行一个，例如：\n总结式结尾\n解释性说教"}
                  />
                </label>

                <label className="mt-6 flex flex-col gap-2 text-sm">
                  额外风格备注
                  <textarea
                    className="min-h-[140px] rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
                    value={customStyleNotes}
                    onChange={(event) => setCustomStyleNotes(event.target.value)}
                    placeholder="例如：避免过多总结句；情绪不直接说破，让动作和停顿承担压力。"
                  />
                </label>

                {error ? (
                  <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                ) : null}

                {success ? (
                  <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    {success}
                  </div>
                ) : null}

                <button
                  className="mt-6 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                >
                  {saving ? "保存中..." : "保存偏好"}
                </button>
              </>
            )}
          </div>

          <aside className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <h2 className="text-xl font-semibold">当前状态</h2>
            {!profile ? (
              <p className="mt-4 text-sm leading-7 text-black/60">
                偏好配置加载后，这里会显示当前完成度和系统会如何使用这些设定。
              </p>
            ) : (
              <>
                <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  当前完成度：{(profile.completion_score * 100).toFixed(0)}%
                </p>
                {profile.active_template ? (
                  <p className="mt-4 rounded-2xl border border-copper/20 bg-[#f6ede3] px-4 py-3 text-sm text-copper">
                    激活模板：{profile.active_template.name} / {profile.active_template.tagline}
                  </p>
                ) : (
                  <p className="mt-4 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-black/55">
                    当前未激活模板，生成将直接读取手动配置和学习信号。
                  </p>
                )}
                <div className="mt-4 grid gap-3 text-sm text-black/70">
                  <p>文风：{preferenceValueLabels[profile.prose_style] ?? profile.prose_style}</p>
                  <p>
                    叙事视角：
                    {preferenceValueLabels[profile.narrative_mode] ?? profile.narrative_mode}
                  </p>
                  <p>
                    节奏：
                    {preferenceValueLabels[profile.pacing_preference] ?? profile.pacing_preference}
                  </p>
                  <p>
                    对话比例：
                    {preferenceValueLabels[profile.dialogue_preference] ?? profile.dialogue_preference}
                  </p>
                  <p>
                    张力：
                    {preferenceValueLabels[profile.tension_preference] ?? profile.tension_preference}
                  </p>
                  <p>
                    感官密度：
                    {preferenceValueLabels[profile.sensory_density] ?? profile.sensory_density}
                  </p>
                </div>
              </>
            )}

            <div className="mt-6 rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
              <p className="text-sm font-medium">系统使用方式</p>
              <div className="mt-3 grid gap-2 text-sm leading-7 text-black/65">
                <p>1. `architect` 会根据你的节奏、张力和视角偏好调整章节规划。</p>
                <p>2. `writer` 会根据文风、对话比例和感官密度改写正文落点。</p>
                <p>3. `editor` 会在修订时尝试规避你显式禁用的表达。</p>
                <p>4. 当显式配置还比较稀疏时，系统会参考最近的人工改写信号补全默认项。</p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-black/10 bg-white p-4">
              <p className="text-sm font-medium">自动学习信号</p>
              {!profile || profile.learning_snapshot.observation_count === 0 ? (
                <p className="mt-3 text-sm leading-7 text-black/60">
                  还没有可用观察。后续在章节工作区进行手动保存或回滚后，这里会显示系统识别到的稳定风格信号。
                </p>
              ) : (
                <>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper">
                      观察次数 {profile.learning_snapshot.observation_count}
                    </span>
                    <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                      最近观察 {formatDateTime(profile.learning_snapshot.last_observed_at)}
                    </span>
                  </div>

                  {profile.learning_snapshot.summary ? (
                    <p className="mt-4 text-sm leading-7 text-black/70">
                      {profile.learning_snapshot.summary}
                    </p>
                  ) : null}

                  {profile.learning_snapshot.stable_preferences.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {profile.learning_snapshot.stable_preferences.map((signal) => (
                        <span
                          key={`${signal.field}:${signal.value}`}
                          className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/65"
                        >
                          {learningFieldLabels[signal.field] ?? signal.field}
                          {" "}
                          {preferenceValueLabels[signal.value] ?? signal.value}
                          {" · "}
                          {(signal.confidence * 100).toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {profile.learning_snapshot.favored_elements.length > 0 ? (
                    <p className="mt-4 text-sm leading-7 text-black/70">
                      高频保留元素：{profile.learning_snapshot.favored_elements.join(" / ")}
                    </p>
                  ) : null}

                  {Object.keys(profile.learning_snapshot.source_breakdown).length > 0 ? (
                    <p className="mt-3 text-xs leading-6 text-black/50">
                      来源：
                      {" "}
                      {Object.entries(profile.learning_snapshot.source_breakdown)
                        .map(([key, count]) => `${observationSourceLabels[key] ?? key} ${count}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
