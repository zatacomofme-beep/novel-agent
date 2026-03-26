"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { StyleTemplate, UserPreferenceProfile } from "@/types/api";

export type StylePreferencePayload = {
  prose_style: string;
  narrative_mode: string;
  pacing_preference: string;
  dialogue_preference: string;
  tension_preference: string;
  sensory_density: string;
  favored_elements: string[];
  banned_patterns: string[];
  custom_style_notes: string | null;
};

type StyleControlPanelProps = {
  chapterSample: string;
  mode?: "story-room" | "center";
  secondaryActionHref?: string | null;
  secondaryActionLabel?: string | null;
  preferenceProfile: UserPreferenceProfile | null;
  styleTemplates: StyleTemplate[];
  loading: boolean;
  actionKey: string | null;
  onChapterSampleChange: (value: string) => void;
  onApplyTemplate: (templateKey: string) => void;
  onClearTemplate: () => void;
  onSavePreference: (payload: StylePreferencePayload) => void;
};

const OPTION_LABELS: Record<string, string> = {
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

const FIELD_OPTIONS = {
  prose_style: [
    { value: "precise", label: "精确克制" },
    { value: "lyrical", label: "抒情流动" },
    { value: "sharp", label: "冷峻锋利" },
  ],
  narrative_mode: [
    { value: "close_third", label: "贴身第三人称" },
    { value: "omniscient", label: "多点俯瞰" },
    { value: "first_person", label: "第一人称" },
  ],
  pacing_preference: [
    { value: "fast", label: "快推进" },
    { value: "balanced", label: "平衡推进" },
    { value: "slow_burn", label: "慢燃积压" },
  ],
  dialogue_preference: [
    { value: "dialogue_forward", label: "对话驱动" },
    { value: "balanced", label: "对话叙述平衡" },
    { value: "narration_heavy", label: "叙述主导" },
  ],
  tension_preference: [
    { value: "restrained", label: "克制蓄压" },
    { value: "balanced", label: "张弛平衡" },
    { value: "high_tension", label: "高压逼近" },
  ],
  sensory_density: [
    { value: "minimal", label: "稀疏点染" },
    { value: "focused", label: "重点锚点" },
    { value: "immersive", label: "沉浸细节" },
  ],
} as const;

function parseSlashList(value: string): string[] {
  return value
    .split(/[\n/、；;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatFieldValue(value: string | null | undefined): string {
  if (!value) {
    return "未设定";
  }
  return OPTION_LABELS[value] ?? value;
}

function FieldLabel({ label }: { label: string }) {
  return <span className="text-sm text-black/60">{label}</span>;
}

export function StyleControlPanel({
  chapterSample,
  mode = "story-room",
  secondaryActionHref,
  secondaryActionLabel,
  preferenceProfile,
  styleTemplates,
  loading,
  actionKey,
  onChapterSampleChange,
  onApplyTemplate,
  onClearTemplate,
  onSavePreference,
}: StyleControlPanelProps) {
  const [proseStyle, setProseStyle] = useState("precise");
  const [narrativeMode, setNarrativeMode] = useState("close_third");
  const [pacingPreference, setPacingPreference] = useState("balanced");
  const [dialoguePreference, setDialoguePreference] = useState("balanced");
  const [tensionPreference, setTensionPreference] = useState("balanced");
  const [sensoryDensity, setSensoryDensity] = useState("focused");
  const [favoredElementsText, setFavoredElementsText] = useState("");
  const [bannedPatternsText, setBannedPatternsText] = useState("");
  const [customStyleNotes, setCustomStyleNotes] = useState("");

  useEffect(() => {
    if (!preferenceProfile) {
      return;
    }
    setProseStyle(preferenceProfile.prose_style);
    setNarrativeMode(preferenceProfile.narrative_mode);
    setPacingPreference(preferenceProfile.pacing_preference);
    setDialoguePreference(preferenceProfile.dialogue_preference);
    setTensionPreference(preferenceProfile.tension_preference);
    setSensoryDensity(preferenceProfile.sensory_density);
    setFavoredElementsText(preferenceProfile.favored_elements.join(" / "));
    setBannedPatternsText(preferenceProfile.banned_patterns.join(" / "));
    setCustomStyleNotes(preferenceProfile.custom_style_notes ?? "");
  }, [preferenceProfile]);

  function isRunning(key: string): boolean {
    return actionKey === key;
  }

  function handleSave() {
    onSavePreference({
      prose_style: proseStyle,
      narrative_mode: narrativeMode,
      pacing_preference: pacingPreference,
      dialogue_preference: dialoguePreference,
      tension_preference: tensionPreference,
      sensory_density: sensoryDensity,
      favored_elements: parseSlashList(favoredElementsText),
      banned_patterns: parseSlashList(bannedPatternsText),
      custom_style_notes: customStyleNotes.trim() || null,
    });
  }

  const isCenterMode = mode === "center";
  const eyebrow = isCenterMode ? "风格中心" : "声音设置";
  const title = isCenterMode ? "先把整本书的声音定稳" : "本章样文 + 整本书手感";
  const sampleTitle = isCenterMode ? "风格样文参考" : "这一章的声音参考";
  const samplePlaceholder = isCenterMode
    ? "贴一段最能代表你想要的笔感、节奏和句式气口。"
    : "贴一小段你自己的正文。";
  const sampleScopeHint = isCenterMode ? "这里只是校准参考，不会直接写进正文" : "只影响这一章";

  return (
    <section
      id="voice-settings"
      className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-copper">{eyebrow}</p>
          <h2 className="mt-2 text-2xl font-semibold">{title}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {preferenceProfile ? (
            <>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700">
                完成度 {(preferenceProfile.completion_score * 100).toFixed(0)}%
              </span>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
                已观察 {preferenceProfile.learning_snapshot.observation_count} 次
              </span>
              {preferenceProfile.active_template ? (
                <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-copper">
                  当前底稿 {preferenceProfile.active_template.name}
                </span>
              ) : null}
            </>
          ) : null}
          {secondaryActionHref && secondaryActionLabel ? (
            <Link
              className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6]"
              href={secondaryActionHref}
            >
              {secondaryActionLabel}
            </Link>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="mt-6 rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5 text-sm text-black/55">
          正在整理手感...
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <p className="text-sm font-semibold">{sampleTitle}</p>
            <textarea
              className="mt-4 min-h-[180px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
              placeholder={samplePlaceholder}
              value={chapterSample}
              onChange={(event) => onChapterSampleChange(event.target.value)}
            />
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
              <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                {chapterSample.trim().length > 0 ? `已贴 ${chapterSample.trim().length} 字` : "当前未贴样文"}
              </span>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                {sampleScopeHint}
              </span>
            </div>
          </section>

          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <p className="text-sm font-semibold">整本书当前手感</p>
            {preferenceProfile ? (
              <>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    文风 {formatFieldValue(preferenceProfile.prose_style)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    视角 {formatFieldValue(preferenceProfile.narrative_mode)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    节奏 {formatFieldValue(preferenceProfile.pacing_preference)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    对话 {formatFieldValue(preferenceProfile.dialogue_preference)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    张力 {formatFieldValue(preferenceProfile.tension_preference)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    细节 {formatFieldValue(preferenceProfile.sensory_density)}
                  </span>
                </div>

                {preferenceProfile.learning_snapshot.summary ? (
                  <div className="mt-4 rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm text-black/68">
                    {preferenceProfile.learning_snapshot.summary}
                  </div>
                ) : null}

                {preferenceProfile.learning_snapshot.stable_preferences.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {preferenceProfile.learning_snapshot.stable_preferences
                      .slice(0, 4)
                      .map((signal) => (
                        <span
                          key={`${signal.field}-${signal.value}`}
                          className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55"
                        >
                          {signal.field} · {formatFieldValue(signal.value)}
                        </span>
                        ))}
                  </div>
                ) : null}

                {preferenceProfile.favored_elements.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {preferenceProfile.favored_elements.slice(0, 6).map((item) => (
                      <span
                        key={item}
                        className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                ) : null}
              </>
            ) : null}
          </section>

          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">常用声音底稿</p>
              {preferenceProfile?.active_template ? (
                <button
                  className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/62 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isRunning("style:clear")}
                  onClick={onClearTemplate}
                  type="button"
                >
                  {isRunning("style:clear") ? "清空中..." : "清掉当前底稿"}
                </button>
              ) : null}
            </div>

            <div className="mt-4 space-y-3">
              {styleTemplates.map((template) => (
                <article
                  key={template.key}
                  className={`rounded-[24px] border p-4 ${
                    template.is_active
                      ? "border-copper bg-[#fff7ef]"
                      : "border-black/10 bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold">{template.name}</p>
                        {template.is_active ? (
                          <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-2.5 py-1 text-[11px] text-copper">
                            当前
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm text-black/62">{template.tagline}</p>
                    </div>
                    <button
                      className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/68 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={template.is_active || isRunning(`style:apply:${template.key}`)}
                      onClick={() => onApplyTemplate(template.key)}
                      type="button"
                    >
                      {isRunning(`style:apply:${template.key}`) ? "套用中..." : "套用这套手感"}
                    </button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
                    <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                      文风：{formatFieldValue(template.prose_style)}
                    </span>
                    <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                      节奏：{formatFieldValue(template.pacing_preference)}
                    </span>
                    <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1">
                      张力：{formatFieldValue(template.tension_preference)}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

        <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
          <p className="text-sm font-semibold">长期手感</p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="block">
              <FieldLabel label="句子气口" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={proseStyle}
                onChange={(event) => setProseStyle(event.target.value)}
              >
                {FIELD_OPTIONS.prose_style.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <FieldLabel label="视角距离" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={narrativeMode}
                onChange={(event) => setNarrativeMode(event.target.value)}
              >
                {FIELD_OPTIONS.narrative_mode.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <FieldLabel label="推进速度" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={pacingPreference}
                onChange={(event) => setPacingPreference(event.target.value)}
              >
                {FIELD_OPTIONS.pacing_preference.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <FieldLabel label="对话占比" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={dialoguePreference}
                onChange={(event) => setDialoguePreference(event.target.value)}
              >
                {FIELD_OPTIONS.dialogue_preference.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <FieldLabel label="压迫强度" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={tensionPreference}
                onChange={(event) => setTensionPreference(event.target.value)}
              >
                {FIELD_OPTIONS.tension_preference.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <FieldLabel label="细节密度" />
              <select
                className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                value={sensoryDensity}
                onChange={(event) => setSensoryDensity(event.target.value)}
              >
                {FIELD_OPTIONS.sensory_density.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="mt-4 block">
            <FieldLabel label="你想保留的笔感" />
            <input
              className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
              placeholder="用 / 隔开，比如：动作链 / 潜台词 / 身体反应"
              value={favoredElementsText}
              onChange={(event) => setFavoredElementsText(event.target.value)}
            />
          </label>

          <label className="mt-4 block">
            <FieldLabel label="尽量别出现的套路" />
            <input
              className="mt-2 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
              placeholder="用 / 隔开，比如：总结式结尾 / 解释性说教"
              value={bannedPatternsText}
              onChange={(event) => setBannedPatternsText(event.target.value)}
            />
          </label>

          <label className="mt-4 block">
            <FieldLabel label="额外提醒" />
            <textarea
              className="mt-2 min-h-[140px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
              placeholder="比如：情绪不要一次说透，让动作和停顿自己长出来。"
              value={customStyleNotes}
              onChange={(event) => setCustomStyleNotes(event.target.value)}
            />
          </label>

          <button
            className="mt-5 rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isRunning("style:save")}
            onClick={handleSave}
            type="button"
          >
            {isRunning("style:save") ? "保存中..." : "保存这套手感"}
          </button>
        </section>
      </div>
    </section>
  );
}
