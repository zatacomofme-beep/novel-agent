"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";

import {
  formatAiTaste,
  formatDateTime,
  formatScore,
  formatSignedDelta,
  QualityTrendChart,
  trendDirectionClassName,
  trendDirectionLabel,
} from "@/app/dashboard/_components/quality-trend";
import { ProcessPlaybackPanel, type ProcessPlaybackItem } from "@/components/process-playback-panel";
import { apiFetchWithAuth, downloadWithAuth } from "@/lib/api";
import { clearAuthSession, loadAuthSession } from "@/lib/auth";
import type {
  DashboardFocusItem,
  DashboardOverview,
  DashboardProjectQualityTrend,
  DashboardProjectSummary,
  DashboardRecentTask,
  Project,
  User,
} from "@/types/api";

function buildStoryRoomHref(
  projectId: string,
  options?: {
    stage?: "outline" | "draft" | "final" | "knowledge";
    chapterNumber?: number | null;
    tool?: "review" | null;
  },
): string {
  const params = new URLSearchParams();
  if (options?.stage) {
    params.set("stage", options.stage);
  }
  if (typeof options?.chapterNumber === "number" && Number.isFinite(options.chapterNumber)) {
    params.set("chapter", String(options.chapterNumber));
  }
  if (options?.tool) {
    params.set("tool", options.tool);
  }
  const query = params.toString();
  return `/dashboard/projects/${projectId}/story-room${query ? `?${query}` : ""}`;
}

function buildCollaboratorsHref(projectId: string): string {
  return `/dashboard/projects/${projectId}/collaborators`;
}

function formatCompactCount(value: number): string {
  if (!Number.isFinite(value)) {
    return "0";
  }
  if (value >= 10000) {
    return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}万`;
  }
  return value.toLocaleString("zh-CN");
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function focusRiskClassName(riskLevel: string): string {
  if (riskLevel === "high") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  if (riskLevel === "medium") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function buildFocusItemHref(item: DashboardFocusItem): string {
  return buildStoryRoomHref(item.project_id, {
    stage:
      item.stage === "outline" || item.stage === "final" || item.stage === "knowledge"
        ? item.stage
        : "draft",
    chapterNumber: item.chapter_number,
    tool: item.stage === "draft" && item.focus_type === "risk_review" ? "review" : null,
  });
}

type ProjectPrimaryAction = {
  label: string;
  href: string;
  status: string;
};

function buildProjectPrimaryAction(project: DashboardProjectSummary): ProjectPrimaryAction {
  if (project.chapter_count > 0) {
    return {
      label: "继续写作",
      href: buildStoryRoomHref(project.project_id, {
        stage: "draft",
      }),
      status: project.review_ready_chapters > 0 ? "下一步：继续写正文或收口" : "下一步：继续写正文",
    };
  }

  if (project.has_novel_blueprint) {
    return {
      label: "开始第一章",
      href: buildStoryRoomHref(project.project_id, {
        stage: "draft",
      }),
      status: "下一步：按章纲开始正文",
    };
  }

  return {
    label: "先定三级大纲",
    href: buildStoryRoomHref(project.project_id, {
      stage: "outline",
    }),
    status: project.has_bootstrap_profile
      ? "下一步：先把三级大纲定下来"
      : "下一步：先补基础信息，再把三级大纲定下来",
  };
}

function QualityTrendCard({ trend }: { trend: DashboardProjectQualityTrend }) {
  const primaryRiskChapter =
    trend.chapter_points.find((point) =>
      trend.risk_chapter_numbers.includes(point.chapter_number),
    ) ?? trend.weakest_chapter;
  const weakestChapter =
    trend.weakest_chapter &&
    trend.weakest_chapter.chapter_number !== primaryRiskChapter?.chapter_number
      ? trend.weakest_chapter
      : null;

  return (
    <article className="rounded-3xl border border-black/10 bg-white/80 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{trend.title}</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
              更新 {formatDateTime(trend.updated_at)}
            </span>
            <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
              已评估 {trend.evaluated_chapter_count}/{trend.chapter_count} 章
            </span>
          </div>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs ${trendDirectionClassName(trend.trend_direction)}`}
        >
          {trendDirectionLabel(trend.trend_direction)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">最新评分</p>
          <p className="mt-2 text-sm text-black/70">{formatScore(trend.latest_overall_score)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">趋势变化</p>
          <p className="mt-2 text-sm text-black/70">{formatSignedDelta(trend.score_delta)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">机械感</p>
          <p className="mt-2 text-sm text-black/70">{formatAiTaste(trend.latest_ai_taste_score)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">覆盖率</p>
          <p className="mt-2 text-sm text-black/70">{(trend.coverage_ratio * 100).toFixed(0)}%</p>
        </div>
      </div>

      <div className="mt-4">
        <QualityTrendChart points={trend.chapter_points} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
          协作者 {trend.collaborator_count}
        </span>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
          {trend.access_role}
        </span>
        {trend.chapter_points.map((point) => (
          <span
            key={point.chapter_id}
            className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60"
          >
            Ch{point.chapter_number} {formatScore(point.overall_score)}
          </span>
        ))}
      </div>

      <div className="mt-4">
        {trend.risk_chapter_numbers.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {trend.chapter_points
              .filter((point) => trend.risk_chapter_numbers.includes(point.chapter_number))
              .slice(0, 3)
              .map((point) => (
                <Link
                  key={point.chapter_id}
                  className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700 transition hover:bg-amber-100"
                  href={buildStoryRoomHref(trend.project_id, {
                    stage: "draft",
                    chapterNumber: point.chapter_number,
                    tool: "review",
                  })}
                >
                  回看 Ch{point.chapter_number}
                </Link>
              ))}
          </div>
        ) : (
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
            最近没有高风险章节
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          className="rounded-2xl border border-black/10 bg-[#f6f0e6] px-3 py-2 text-sm font-medium"
          href={buildStoryRoomHref(trend.project_id)}
        >
          进入故事工作台
        </Link>
        {primaryRiskChapter ? (
          <Link
            className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 transition hover:bg-amber-100"
            href={buildStoryRoomHref(trend.project_id, {
              stage: "draft",
              chapterNumber: primaryRiskChapter.chapter_number,
              tool: "review",
            })}
          >
            回看 Ch{primaryRiskChapter.chapter_number}
          </Link>
        ) : null}
        {weakestChapter ? (
          <Link
            className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm font-medium transition hover:bg-[#f6f0e6]"
            href={buildStoryRoomHref(trend.project_id, {
              stage: "draft",
              chapterNumber: weakestChapter.chapter_number,
              tool: "review",
            })}
          >
            看最低分 Ch{weakestChapter.chapter_number}
          </Link>
        ) : null}
      </div>
    </article>
  );
}

const recentTaskTypeLabels: Record<string, string> = {
  chapter_generation: "续写下一章",
  "story_engine.bulk_import": "导入设定",
  "story_engine.outline_stress_test": "测大纲漏洞",
  "story_engine.chapter_stream": "生成正文",
  "story_engine.realtime_guard": "检查正文",
  "story_engine.final_optimize": "终稿收口",
  "entity_generation.characters": "补几个人物",
  "entity_generation.supporting": "补几个配角",
  "entity_generation.items": "补几件物品",
  "entity_generation.locations": "补几个地点",
  "entity_generation.factions": "补一个势力",
  "entity_generation.plot_threads": "补几条剧情线",
};

const recentTaskStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  succeeded: "已完成",
  failed: "已失败",
  paused: "已停住",
};

function formatRecentTaskType(taskType: string): string {
  if (taskType === "chapter_generation") {
    return "兼容正文生成";
  }
  return recentTaskTypeLabels[taskType] ?? taskType.replaceAll(".", " / ");
}

function formatRecentTaskStatus(status: string): string {
  return recentTaskStatusLabels[status] ?? status;
}

function normalizeRecentTaskStatus(
  status: string,
  workflowStatus?: string | null,
): "queued" | "running" | "succeeded" | "failed" | "paused" {
  if (workflowStatus === "paused") {
    return "paused";
  }
  if (status === "queued" || status === "running" || status === "succeeded" || status === "failed") {
    return status;
  }
  return "queued";
}

function buildRecentTaskHref(task: DashboardRecentTask): string | null {
  if (!task.project_id) {
    return null;
  }

  if (task.task_type.startsWith("entity_generation.")) {
    return buildStoryRoomHref(task.project_id, {
      stage: "knowledge",
    });
  }

  if (task.task_type === "story_engine.bulk_import") {
    return buildStoryRoomHref(task.project_id, {
      stage: "knowledge",
    });
  }

  if (task.task_type === "story_engine.outline_stress_test") {
    return buildStoryRoomHref(task.project_id, {
      stage: "outline",
    });
  }

  if (task.task_type === "story_engine.final_optimize") {
    return buildStoryRoomHref(task.project_id, {
      stage: "final",
      chapterNumber: task.chapter_number,
    });
  }

  if (task.task_type === "story_engine.realtime_guard" || task.task_type === "story_engine.chapter_stream") {
    return buildStoryRoomHref(task.project_id, {
      stage: "draft",
      chapterNumber: task.chapter_number,
    });
  }

  return buildStoryRoomHref(task.project_id, {
    stage: "draft",
    chapterNumber: task.chapter_number,
    tool:
      task.task_type === "chapter_generation" && task.chapter_number !== null
        ? "review"
        : null,
  });
}

function buildRecentTaskActionLabel(task: DashboardRecentTask): string {
  if (task.task_type.startsWith("entity_generation.")) {
    return "去设定区";
  }
  if (task.task_type === "story_engine.bulk_import") {
    return "去设定区";
  }
  if (task.task_type === "story_engine.outline_stress_test") {
    return "去大纲区";
  }
  if (task.task_type === "story_engine.final_optimize") {
    return "去终稿区";
  }
  if (task.chapter_number !== null) {
    return `处理 Ch${task.chapter_number}`;
  }
  if (task.task_type === "chapter_generation") {
    return "去正文区";
  }
  return "继续处理";
}

function normalizePositiveNumber(value: number, fallback: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return fallback;
  }
  return Math.round(value);
}

function DashboardPageShell() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const createSectionRef = useRef<HTMLElement | null>(null);
  const titleInputRef = useRef<HTMLInputElement | null>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [tone, setTone] = useState("");
  const [targetTotalWords, setTargetTotalWords] = useState(1_000_000);
  const [targetChapterWords, setTargetChapterWords] = useState(3_000);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [exportingKey, setExportingKey] = useState<string | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);

  useEffect(() => {
    const session = loadAuthSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setCurrentUser(session.user);
    void fetchOverview();
  }, []);

  async function fetchOverview() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchWithAuth<DashboardOverview>("/api/v1/dashboard/overview");
      setOverview(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load dashboard overview.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      const normalizedTotalWords = normalizePositiveNumber(targetTotalWords, 1_000_000);
      const normalizedChapterWords = normalizePositiveNumber(targetChapterWords, 3_000);
      const plannedChapterCount = Math.max(
        10,
        Math.ceil(normalizedTotalWords / normalizedChapterWords),
      );
      const createdProject = await apiFetchWithAuth<Project>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({
          title,
          genre: genre || null,
          tone: tone || null,
          status: "draft",
        }),
      });
      await apiFetchWithAuth(`/api/v1/projects/${createdProject.id}/bootstrap`, {
        method: "PUT",
        body: JSON.stringify({
          genre: genre || null,
          tone: tone || null,
          target_total_words: normalizedTotalWords,
          target_chapter_words: normalizedChapterWords,
          planned_chapter_count: plannedChapterCount,
        }),
      });
      setTitle("");
      setGenre("");
      setTone("");
      setTargetTotalWords(1_000_000);
      setTargetChapterWords(3_000);
      router.push(`/dashboard/projects/${createdProject.id}/story-room?entry=new-book&stage=outline`);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to create project.",
      );
    } finally {
      setCreating(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    setCurrentUser(null);
    setOverview(null);
  }

  async function handleExportProject(projectId: string, format: "md" | "txt") {
    setExportingKey(`${projectId}:${format}`);
    setError(null);
    setSuccess(null);
    try {
      await downloadWithAuth(`/api/v1/projects/${projectId}/export?format=${format}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to export project.",
      );
    } finally {
      setExportingKey(null);
    }
  }

  async function handleDeleteProject(projectId: string, projectTitle: string) {
    const confirmed = window.confirm(
      `确认删除《${projectTitle}》吗？这本书的大纲、正文、设定和导出记录都会一起删除，不能恢复。`,
    );
    if (!confirmed) {
      return;
    }

    setDeletingProjectId(projectId);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<void>(`/api/v1/projects/${projectId}`, {
        method: "DELETE",
      });
      setOverview((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          total_projects: Math.max(0, current.total_projects - 1),
          project_summaries: current.project_summaries.filter(
            (item) => item.project_id !== projectId,
          ),
          project_quality_trends: current.project_quality_trends.filter(
            (item) => item.project_id !== projectId,
          ),
          recent_tasks: current.recent_tasks.filter((item) => item.project_id !== projectId),
        };
      });
      router.refresh();
      await fetchOverview();
      setSuccess(`《${projectTitle}》已经删除。`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to delete project.",
      );
    } finally {
      setDeletingProjectId(null);
    }
  }

  const projectSummaries = overview?.project_summaries ?? [];
  const qualityTrends = overview?.project_quality_trends ?? [];
  const recentTasks = overview?.recent_tasks ?? [];
  const focusQueue = overview?.focus_queue ?? [];
  const genreDistribution = overview?.genre_distribution ?? [];
  const activitySnapshot = overview?.activity_snapshot;
  const qualitySnapshot = overview?.quality_snapshot;
  const taskHealth = overview?.task_health;
  const pipelineSnapshot = overview?.pipeline_snapshot;
  const recentProjectHighlights = projectSummaries.slice(0, 3);
  const projectTitleMap = useMemo(
    () =>
      Object.fromEntries(
        (overview?.project_summaries ?? []).map((project) => [project.project_id, project.title]),
      ),
    [overview?.project_summaries],
  );
  const recentProcessItems = useMemo<ProcessPlaybackItem[]>(() => {
    return recentTasks.map((task) => {
      const taskHref = buildRecentTaskHref(task);
      const projectTitle =
        task.project_id ? projectTitleMap[task.project_id] ?? "当前项目" : "最近过程";

      return {
        id: task.task_id,
        label: formatRecentTaskType(task.task_type),
        title:
          task.chapter_number !== null
            ? `${projectTitle} · Ch${task.chapter_number}`
            : projectTitle,
        summary: task.message ?? "最近过程已记录。",
        status: normalizeRecentTaskStatus(task.status, task.workflow_status),
        progress: task.progress,
        updatedAt: task.updated_at,
        badges: [
          "项目记录",
          ...(task.chapter_number !== null ? [`第 ${task.chapter_number} 章`] : []),
        ],
        steps: [
          {
            id: `${task.task_id}:latest`,
            label:
              task.message ?? formatRecentTaskStatus(task.workflow_status ?? task.status),
            detail: null,
            status: normalizeRecentTaskStatus(task.status, task.workflow_status),
            createdAt: task.updated_at,
          },
        ],
        actionLabel: taskHref ? buildRecentTaskActionLabel(task) : null,
        actionHref: taskHref,
      };
    });
  }, [projectTitleMap, recentTasks]);
  const isFirstBookFlow = searchParams.get("intent") === "new" || projectSummaries.length === 0;
  const plannedChapterCount = Math.max(
    10,
    Math.ceil(
      normalizePositiveNumber(targetTotalWords, 1_000_000) /
        normalizePositiveNumber(targetChapterWords, 3_000),
    ),
  );

  useEffect(() => {
    if (!currentUser || !isFirstBookFlow) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      createSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      titleInputRef.current?.focus();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [currentUser, isFirstBookFlow]);

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="text-sm uppercase tracking-[0.24em] text-copper">书架</p>
          <h1 className="mt-3 text-3xl font-semibold">尚未登录</h1>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper"
              href="/login"
            >
              去登录
            </Link>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              href="/register"
            >
              去注册
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section
          ref={createSectionRef}
          className="rounded-[36px] border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur"
        >
          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <div className="flex flex-col justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-copper">创建新书</p>
                <h1 className="mt-3 text-4xl font-semibold">
                  {isFirstBookFlow ? "先创建第一本书" : "创建下一本书"}
                </h1>
                <p className="mt-4 max-w-xl text-sm leading-7 text-black/62">
                  设好书名、体量和题材，就直接去定三级大纲。
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                    {currentUser.email}
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                    书名
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                    总字数
                  </span>
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                    三级大纲
                  </span>
                </div>
              </div>

              <div className="mt-6 rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4 text-sm text-black/62">
                创建完成后，直接进入这本书的三级大纲。
              </div>
            </div>

            <form
              id="create-project"
              className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-6"
              onSubmit={handleCreate}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">新书信息</p>
                  <h2 className="mt-2 text-2xl font-semibold">填完就去定大纲</h2>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium transition hover:bg-[#f6f0e6]"
                    href="/dashboard/preferences"
                  >
                    风格中心
                  </Link>
                  <button
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
                    onClick={handleLogout}
                    type="button"
                  >
                    退出登录
                  </button>
                </div>
              </div>

              <div className="mt-6 grid gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  书名
                  <input
                    ref={titleInputRef}
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="例如：海城夜潮"
                    required
                  />
                </label>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm">
                    总字数
                    <input
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      type="number"
                      min={50000}
                      step={10000}
                      value={targetTotalWords}
                      onChange={(event) =>
                        setTargetTotalWords(Number(event.target.value || 1_000_000))
                      }
                    />
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    单章目标字数
                    <input
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      type="number"
                      min={1000}
                      step={500}
                      value={targetChapterWords}
                      onChange={(event) =>
                        setTargetChapterWords(Number(event.target.value || 3_000))
                      }
                    />
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm">
                    小说类别
                    <input
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={genre}
                      onChange={(event) => setGenre(event.target.value)}
                      placeholder="科幻 / 悬疑 / 奇幻..."
                    />
                  </label>

                  <label className="flex flex-col gap-2 text-sm">
                    气质
                    <input
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={tone}
                      onChange={(event) => setTone(event.target.value)}
                      placeholder="热血 / 冷峻 / 轻快..."
                    />
                  </label>
                </div>

                <div className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-black/62">
                  预计约 {plannedChapterCount} 章
                </div>
              </div>

              <button
                className="mt-6 w-full rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={creating}
              >
                {creating ? "创建中..." : "创建新书并去定大纲"}
              </button>
            </form>
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

        <section
          id="recent-projects"
          className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">继续写这几本</h2>
            </div>
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
              type="button"
              onClick={() => void fetchOverview()}
            >
              刷新
            </button>
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-black/60">正在整理最近项目...</p>
          ) : null}

          {!loading && recentProjectHighlights.length === 0 ? (
            <p className="mt-6 text-sm text-black/60">创建第一本书后，这里会显示最近项目。</p>
          ) : null}

          <div className="mt-6 grid gap-4 xl:grid-cols-3">
            {recentProjectHighlights.map((project) => {
              const primaryAction = buildProjectPrimaryAction(project);
              return (
                <article
                  key={`highlight-${project.project_id}`}
                  className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold">{project.title}</h3>
                      <p className="mt-2 text-sm text-black/62">
                        {project.genre ?? "未设置题材"}
                        {" · "}
                        {project.status}
                      </p>
                      <p className="mt-2 text-sm text-black/50">
                        最近更新 {formatDateTime(project.updated_at)}
                      </p>
                    </div>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                      章节 {project.chapter_count}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs text-black/55">
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      {primaryAction.status}
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      体量 {project.word_count} 字
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                      协作 {project.collaborator_count} 人
                    </span>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-3">
                    <Link
                      className="inline-flex rounded-2xl border border-black/10 bg-[#f6f0e6] px-4 py-3 text-sm font-medium transition hover:bg-[#efe4d4]"
                      href={primaryAction.href}
                    >
                      {primaryAction.label}
                    </Link>
                    <Link
                      className="inline-flex rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium transition hover:bg-[#f6f0e6]"
                      href={buildCollaboratorsHref(project.project_id)}
                    >
                      协作成员
                    </Link>
                  </div>
                  {project.access_role === "owner" ? (
                    <button
                      className="mt-3 inline-flex rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleDeleteProject(project.project_id, project.title)}
                      disabled={deletingProjectId === project.project_id}
                    >
                      {deletingProjectId === project.project_id ? "删除中..." : "删除这本书"}
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>

        <details className="rounded-[32px] border border-black/10 bg-white/72 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
          <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-copper">进阶看板</p>
              <h2 className="mt-2 text-xl font-semibold">更多状态</h2>
            </div>
            <span className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm text-black/65">
              展开
            </span>
          </summary>

          <div className="mt-6 space-y-6">
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <p className="text-sm text-black/55">近 7 天活跃项目</p>
                <p className="mt-3 text-3xl font-semibold">
                  {activitySnapshot?.active_projects_last_7_days ?? 0}
                </p>
                <p className="mt-2 text-xs text-black/45">
                  全部项目 {overview?.total_projects ?? 0} 本
                </p>
              </article>
              <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <p className="text-sm text-black/55">近 7 天更新章节</p>
                <p className="mt-3 text-3xl font-semibold">
                  {activitySnapshot?.chapters_updated_last_7_days ?? 0}
                </p>
                <p className="mt-2 text-xs text-black/45">
                  最近活跃字数 {formatCompactCount(activitySnapshot?.active_words_last_7_days ?? 0)}
                </p>
              </article>
              <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <p className="text-sm text-black/55">待收口章节</p>
                <p className="mt-3 text-3xl font-semibold">
                  {overview?.review_ready_chapters ?? 0}
                </p>
                <p className="mt-2 text-xs text-black/45">
                  近 30 天确认终稿 {activitySnapshot?.final_chapters_last_30_days ?? 0} 章
                </p>
              </article>
              <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <p className="text-sm text-black/55">风险章节</p>
                <p className="mt-3 text-3xl font-semibold">
                  {qualitySnapshot?.risk_chapter_count ?? 0}
                </p>
                <p className="mt-2 text-xs text-black/45">
                  走低项目 {qualitySnapshot?.declining_project_count ?? 0} 本
                </p>
              </article>
            </section>

            <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
              <div className="grid gap-6">
                <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-xl font-semibold">当前最该处理</h2>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                      {focusQueue.length} 条
                    </span>
                  </div>

                  {loading ? (
                    <p className="mt-4 text-sm text-black/60">整理当前优先级...</p>
                  ) : null}

                  {!loading && focusQueue.length === 0 ? (
                    <p className="mt-4 text-sm text-black/60">创建第一本书后，这里会给你下一步。</p>
                  ) : null}

                  <div className="mt-4 grid gap-3">
                    {focusQueue.map((item) => (
                      <article
                        key={`${item.project_id}:${item.focus_type}:${item.chapter_number ?? "none"}`}
                        className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-black/82">{item.title}</p>
                            <p className="mt-2 text-sm text-black/68">{item.reason}</p>
                          </div>
                          <span
                            className={`rounded-full border px-3 py-1 text-xs ${focusRiskClassName(item.risk_level)}`}
                          >
                            {item.risk_level === "high"
                              ? "先处理"
                              : item.risk_level === "medium"
                                ? "尽快推进"
                                : "可继续"}
                          </span>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <span className="text-xs text-black/45">
                            更新于 {formatDateTime(item.updated_at)}
                          </span>
                          {item.genre ? (
                            <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                              {item.genre}
                            </span>
                          ) : null}
                          <Link
                            className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs font-medium text-black/72 transition hover:bg-[#f6f0e6]"
                            href={buildFocusItemHref(item)}
                          >
                            {item.action_label}
                          </Link>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-xl font-semibold">阶段与任务</h2>
                    <button
                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                      type="button"
                      onClick={() => void fetchOverview()}
                    >
                      刷新
                    </button>
                  </div>

                  {loading ? (
                    <p className="mt-4 text-sm text-black/60">整理阶段与任务状态...</p>
                  ) : null}

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">项目阶段</p>
                      <div className="mt-3 grid gap-2 text-sm text-black/72">
                        <div className="flex items-center justify-between gap-3">
                          <span>待定大纲</span>
                          <span>{pipelineSnapshot?.outline_pending_projects ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>待开第一章</span>
                          <span>{pipelineSnapshot?.ready_for_first_chapter_projects ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>正在写作</span>
                          <span>{pipelineSnapshot?.writing_in_progress_projects ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>待确认终稿</span>
                          <span>{pipelineSnapshot?.awaiting_finalization_projects ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>稳定输出</span>
                          <span>{pipelineSnapshot?.stable_output_projects ?? 0}</span>
                        </div>
                      </div>
                    </article>

                    <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">任务健康</p>
                      <div className="mt-3 grid gap-2 text-sm text-black/72">
                        <div className="flex items-center justify-between gap-3">
                          <span>运行中</span>
                          <span>{taskHealth?.running_count ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>排队中</span>
                          <span>{taskHealth?.queued_count ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>失败</span>
                          <span>{taskHealth?.failed_count ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>卡住</span>
                          <span>{taskHealth?.stalled_active_task_count ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>近期待失败</span>
                          <span>{taskHealth?.recent_failed_task_count ?? 0}</span>
                        </div>
                      </div>
                    </article>
                  </div>
                </section>

                <ProcessPlaybackPanel
                  title="最近发生了什么"
                  subtitle="用来快速看到哪本书刚跑完、还在处理中，或者卡在了哪一步。"
                  items={recentProcessItems}
                  emptyTitle={loading ? "正在整理最近过程" : "暂时没有过程记录"}
                  emptyDescription={
                    loading
                      ? "稍等一下，书架正在汇总最近的处理记录。"
                      : "开始起稿、补设定或处理章节后，这里会自动出现最近过程。"
                  }
                />
              </div>

              <section className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold">最近写作走势</h2>
                  </div>
                  <button
                    className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                    type="button"
                    onClick={() => void fetchOverview()}
                  >
                    刷新走势
                  </button>
                </div>

                {loading ? (
                  <p className="mt-6 text-sm text-black/60">加载趋势视图中...</p>
                ) : null}

                {!loading && qualityTrends.length === 0 ? (
                  <p className="mt-6 text-sm text-black/60">还没有趋势数据。</p>
                ) : null}

                <div className="mt-6 grid gap-4 xl:grid-cols-2">
                  {qualityTrends.map((trend) => (
                    <QualityTrendCard key={trend.project_id} trend={trend} />
                  ))}
                </div>
              </section>
            </section>

            <section className="grid gap-4 xl:grid-cols-3">
              <article className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <h2 className="text-xl font-semibold">质量快照</h2>
                <div className="mt-4 grid gap-3 text-sm text-black/72">
                  <div className="flex items-center justify-between gap-3">
                    <span>上升项目</span>
                    <span>{qualitySnapshot?.improving_project_count ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>走低项目</span>
                    <span>{qualitySnapshot?.declining_project_count ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>机械感偏高章节</span>
                    <span>{qualitySnapshot?.high_ai_taste_chapter_count ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>评分覆盖率</span>
                    <span>{formatPercent(qualitySnapshot?.average_coverage_ratio)}</span>
                  </div>
                </div>
              </article>

              <article className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <h2 className="text-xl font-semibold">题材分布</h2>
                {loading ? (
                  <p className="mt-4 text-sm text-black/60">整理题材分布中...</p>
                ) : null}
                {!loading && genreDistribution.length === 0 ? (
                  <p className="mt-4 text-sm text-black/60">还没有题材数据。</p>
                ) : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  {genreDistribution.map((item) => (
                    <span
                      key={item.genre}
                      className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/65"
                    >
                      {item.genre} · {item.project_count}
                    </span>
                  ))}
                </div>
              </article>

              <article className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
                <h2 className="text-xl font-semibold">书架状态</h2>
                <div className="mt-4 grid gap-3 text-sm text-black/72">
                  <div className="flex items-center justify-between gap-3">
                    <span>近 30 天新开书</span>
                    <span>{activitySnapshot?.new_projects_last_30_days ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>14 天未更新</span>
                    <span>{activitySnapshot?.stale_projects_last_14_days ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>总字数</span>
                    <span>{formatCompactCount(overview?.total_words ?? 0)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>总任务数</span>
                    <span>{formatCompactCount(taskHealth?.total_task_count ?? 0)}</span>
                  </div>
                </div>
              </article>
            </section>

            <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">全部项目</h2>
                </div>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                  type="button"
                  onClick={() => void fetchOverview()}
                >
                  刷新
                </button>
              </div>

              {loading ? (
                <p className="mt-6 text-sm text-black/60">加载项目概览中...</p>
              ) : null}

              {!loading && projectSummaries.length === 0 ? (
                <p className="mt-6 text-sm text-black/60">还没有项目。</p>
              ) : null}

              <div className="mt-6 grid gap-4">
                {projectSummaries.map((project) => {
                  const primaryAction = buildProjectPrimaryAction(project);
                  return (
                    <article
                      key={project.project_id}
                      className="rounded-2xl border border-black/10 bg-white/80 p-5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h3 className="text-lg font-semibold">{project.title}</h3>
                          <p className="mt-2 text-sm text-black/62">
                            {project.genre ?? "未设置题材"}
                            {" · "}
                            更新 {formatDateTime(project.updated_at)}
                          </p>
                        </div>
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${trendDirectionClassName(project.trend_direction)}`}
                        >
                          {trendDirectionLabel(project.trend_direction)}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          {primaryAction.status}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          章节 {project.chapter_count}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          待收口 {project.review_ready_chapters}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          协作 {project.collaborator_count} 人
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          终稿 {project.final_chapters}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          评分 {formatScore(project.average_overall_score)}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <Link
                          className="rounded-2xl border border-black/10 bg-[#f6f0e6] px-3 py-2 text-sm font-medium"
                          href={primaryAction.href}
                        >
                          {primaryAction.label}
                        </Link>
                        <Link
                          className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm font-medium transition hover:bg-[#f6f0e6]"
                          href={buildCollaboratorsHref(project.project_id)}
                        >
                          协作成员
                        </Link>
                        <button
                          className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                          type="button"
                          onClick={() => void handleExportProject(project.project_id, "md")}
                          disabled={exportingKey === `${project.project_id}:md`}
                        >
                          {exportingKey === `${project.project_id}:md` ? "导出中..." : "导出 MD"}
                        </button>
                        <button
                          className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                          type="button"
                          onClick={() => void handleExportProject(project.project_id, "txt")}
                          disabled={exportingKey === `${project.project_id}:txt`}
                        >
                          {exportingKey === `${project.project_id}:txt` ? "导出中..." : "导出 TXT"}
                        </button>
                        {project.access_role === "owner" ? (
                          <button
                            className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                            type="button"
                            onClick={() => void handleDeleteProject(project.project_id, project.title)}
                            disabled={deletingProjectId === project.project_id}
                          >
                            {deletingProjectId === project.project_id ? "删除中..." : "删除项目"}
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          </div>
        </details>
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen px-6 py-10">
          <div className="mx-auto max-w-7xl rounded-[36px] border border-black/10 bg-white/75 p-10 text-sm text-black/55">
            正在装载你的项目工作台...
          </div>
        </main>
      }
    >
      <DashboardPageShell />
    </Suspense>
  );
}
