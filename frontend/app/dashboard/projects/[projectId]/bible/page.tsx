"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import type {
  StoryBible,
  CharacterItem,
  ForeshadowingItem,
  LocationItem,
  PlotThreadItem,
  TimelineEventItem,
  WorldSettingItem,
} from "@/types/api";

type JsonSectionKey =
  | "characters"
  | "world_settings"
  | "locations"
  | "plot_threads"
  | "foreshadowing"
  | "timeline_events";

type StoryBiblePayload = {
  project: {
    title: string;
    genre: string | null;
    theme: string | null;
    tone: string | null;
    status: string;
  };
  characters: CharacterItem[];
  world_settings: WorldSettingItem[];
  locations: LocationItem[];
  plot_threads: PlotThreadItem[];
  foreshadowing: ForeshadowingItem[];
  timeline_events: TimelineEventItem[];
};

function parseJsonSection<T>(label: string, raw: string): T[] {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error(`${label} must be a JSON array.`);
    }
    return parsed as T[];
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Invalid JSON.";
    throw new Error(`${label} parse failed: ${reason}`);
  }
}

export default function StoryBiblePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [bible, setBible] = useState<StoryBible | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [theme, setTheme] = useState("");
  const [tone, setTone] = useState("");
  const [status, setStatus] = useState("draft");
  const [charactersText, setCharactersText] = useState("[]");
  const [worldSettingsText, setWorldSettingsText] = useState("[]");
  const [locationsText, setLocationsText] = useState("[]");
  const [plotThreadsText, setPlotThreadsText] = useState("[]");
  const [foreshadowingText, setForeshadowingText] = useState("[]");
  const [timelineText, setTimelineText] = useState("[]");

  const fetchBible = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<StoryBible>(
        `/api/v1/projects/${projectId}/bible`,
      );
      setBible(data);
      setTitle(data.project.title);
      setGenre(data.project.genre ?? "");
      setTheme(data.project.theme ?? "");
      setTone(data.project.tone ?? "");
      setStatus(data.project.status);
      setCharactersText(JSON.stringify(data.characters, null, 2));
      setWorldSettingsText(JSON.stringify(data.world_settings, null, 2));
      setLocationsText(JSON.stringify(data.locations, null, 2));
      setPlotThreadsText(JSON.stringify(data.plot_threads, null, 2));
      setForeshadowingText(JSON.stringify(data.foreshadowing, null, 2));
      setTimelineText(JSON.stringify(data.timeline_events, null, 2));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load story bible.",
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchBible();
  }, [fetchBible]);

  const sectionSummaries = useMemo(
    () => [
      { label: "人物", value: bible?.characters.length ?? 0 },
      { label: "世界设定", value: bible?.world_settings.length ?? 0 },
      { label: "地点", value: bible?.locations.length ?? 0 },
      { label: "剧情线", value: bible?.plot_threads.length ?? 0 },
      { label: "伏笔", value: bible?.foreshadowing.length ?? 0 },
      { label: "时间线", value: bible?.timeline_events.length ?? 0 },
    ],
    [bible],
  );
  const canEditProject =
    bible?.project.access_role === "owner" || bible?.project.access_role === "editor";

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const payload: StoryBiblePayload = {
        project: {
          title,
          genre: genre || null,
          theme: theme || null,
          tone: tone || null,
          status,
        },
        characters: parseJsonSection<CharacterItem>("characters", charactersText),
        world_settings: parseJsonSection<WorldSettingItem>(
          "world_settings",
          worldSettingsText,
        ),
        locations: parseJsonSection<LocationItem>("locations", locationsText),
        plot_threads: parseJsonSection<PlotThreadItem>(
          "plot_threads",
          plotThreadsText,
        ),
        foreshadowing: parseJsonSection<ForeshadowingItem>(
          "foreshadowing",
          foreshadowingText,
        ),
        timeline_events: parseJsonSection<TimelineEventItem>(
          "timeline_events",
          timelineText,
        ),
      };

      const updated = await apiFetchWithAuth<StoryBible>(
        `/api/v1/projects/${projectId}/bible`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      setBible(updated);
      setCharactersText(JSON.stringify(updated.characters, null, 2));
      setWorldSettingsText(JSON.stringify(updated.world_settings, null, 2));
      setLocationsText(JSON.stringify(updated.locations, null, 2));
      setPlotThreadsText(JSON.stringify(updated.plot_threads, null, 2));
      setForeshadowingText(JSON.stringify(updated.foreshadowing, null, 2));
      setTimelineText(JSON.stringify(updated.timeline_events, null, 2));
      setSuccess("Story Bible 已保存。");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to save story bible.",
      );
    } finally {
      setSaving(false);
    }
  }

  function renderJsonPanel(
    key: JsonSectionKey,
    label: string,
    helper: string,
    value: string,
    onChange: (nextValue: string) => void,
  ) {
    return (
      <section
        key={key}
        className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">{label}</h2>
            <p className="mt-2 text-sm leading-7 text-black/65">{helper}</p>
          </div>
        </div>
        <textarea
          className="mt-6 min-h-[260px] w-full rounded-2xl border border-black/10 bg-[#fbfaf5] p-4 font-mono text-sm leading-7 outline-none transition focus:border-copper"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={!canEditProject}
        />
      </section>
    );
  }

  if (loading) {
    return (
      <main className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-6xl rounded-3xl border border-black/10 bg-white/75 p-8">
          <p className="text-sm text-black/65">正在加载 Story Bible...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Story Bible
              </p>
              <h1 className="mt-3 text-4xl font-semibold">{title || "未命名项目"}</h1>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-black/65">
                这一版先把 Story Bible 做成“结构化项目字段 + 各分区 JSON 工作区”。后续可以逐步把每个分区替换成更强的实体编辑器。
              </p>
              {bible ? (
                <p className="mt-3 text-sm leading-7 text-black/55">
                  当前角色：{bible.project.access_role}
                  {bible.project.owner_email ? ` · Owner ${bible.project.owner_email}` : ""}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href="/dashboard"
              >
                返回仪表板
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/chapters`}
              >
                进入章节工作区
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/collaborators`}
              >
                协作者
              </Link>
              <button
                className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || !canEditProject}
              >
                {saving ? "保存中..." : "保存 Story Bible"}
              </button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            {sectionSummaries.map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-black/10 bg-white/70 p-4"
              >
                <p className="text-sm text-black/60">{item.label}</p>
                <p className="mt-2 text-2xl font-semibold">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
          <div className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <h2 className="text-xl font-semibold">项目基础信息</h2>
            {!canEditProject ? (
              <p className="mt-3 text-sm leading-7 text-amber-700">
                当前角色只有查看权限，不能修改 Story Bible。
              </p>
            ) : null}
            <div className="mt-6 flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-sm">
                标题
                <input
                  className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  disabled={!canEditProject}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                类型
                <input
                  className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                  value={genre}
                  onChange={(event) => setGenre(event.target.value)}
                  disabled={!canEditProject}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                主题
                <textarea
                  className="min-h-[120px] rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                  value={theme}
                  onChange={(event) => setTheme(event.target.value)}
                  disabled={!canEditProject}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                语气
                <input
                  className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                  value={tone}
                  onChange={(event) => setTone(event.target.value)}
                  disabled={!canEditProject}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                状态
                <select
                  className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  disabled={!canEditProject}
                >
                  <option value="draft">draft</option>
                  <option value="planning">planning</option>
                  <option value="writing">writing</option>
                  <option value="review">review</option>
                  <option value="published">published</option>
                </select>
              </label>
            </div>

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
          </div>

          <div className="grid gap-6">
            {renderJsonPanel(
              "characters",
              "人物档案",
              "为每个人物提供 name、version、created_chapter 和 data 对象。",
              charactersText,
              setCharactersText,
            )}
            {renderJsonPanel(
              "world_settings",
              "世界设定",
              "每项应包含 key、title、version 和 data 对象。",
              worldSettingsText,
              setWorldSettingsText,
            )}
            {renderJsonPanel(
              "locations",
              "地点",
              "每项应包含 name、version 和 data 对象。",
              locationsText,
              setLocationsText,
            )}
            {renderJsonPanel(
              "plot_threads",
              "剧情线",
              "每项应包含 title、status、importance 和 data 对象。",
              plotThreadsText,
              setPlotThreadsText,
            )}
            {renderJsonPanel(
              "foreshadowing",
              "伏笔",
              "每项应包含 content、status、importance 以及章节位置字段。",
              foreshadowingText,
              setForeshadowingText,
            )}
            {renderJsonPanel(
              "timeline_events",
              "时间线",
              "每项应包含 title、chapter_number 和 data 对象。",
              timelineText,
              setTimelineText,
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
