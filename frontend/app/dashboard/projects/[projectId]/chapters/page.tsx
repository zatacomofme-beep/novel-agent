"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiFetchWithAuth, downloadWithAuth } from "@/lib/api";
import type { Chapter, ProjectStructure } from "@/types/api";

type StructureSelection = {
  branchId: string | null;
  volumeId: string | null;
};

function formatFinalGateStatus(status: string): string {
  if (status === "blocked_rejected") {
    return "Final 阻塞 / rejected";
  }
  if (status === "blocked_review") {
    return "Final 阻塞 / review";
  }
  if (status === "blocked_pending") {
    return "Final 阻塞 / pending";
  }
  return "Final 可放行";
}

function finalGateTone(status: string): string {
  if (status === "blocked_rejected") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_review") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_pending") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function formatReviewVerdict(verdict: string): string {
  if (verdict === "approved") {
    return "已通过";
  }
  if (verdict === "blocked") {
    return "阻塞";
  }
  if (verdict === "changes_requested") {
    return "需修改";
  }
  return verdict;
}

export default function ProjectChaptersPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [structure, setStructure] = useState<ProjectStructure | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [selectedVolumeId, setSelectedVolumeId] = useState<string | null>(null);
  const [chapterNumber, setChapterNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [volumeTitle, setVolumeTitle] = useState("");
  const [volumeSummary, setVolumeSummary] = useState("");
  const [branchTitle, setBranchTitle] = useState("");
  const [branchKey, setBranchKey] = useState("");
  const [branchDescription, setBranchDescription] = useState("");
  const [branchSourceId, setBranchSourceId] = useState("");
  const [branchCopyChapters, setBranchCopyChapters] = useState(true);
  const [branchAsDefault, setBranchAsDefault] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStructure, setLoadingStructure] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [creatingChapter, setCreatingChapter] = useState(false);
  const [creatingVolume, setCreatingVolume] = useState(false);
  const [creatingBranch, setCreatingBranch] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"md" | "txt" | null>(null);

  const applyStructure = useCallback(
    (
      nextStructure: ProjectStructure,
      preferred: Partial<StructureSelection> = {},
    ) => {
      setStructure(nextStructure);

      const availableBranchIds = new Set(nextStructure.branches.map((branch) => branch.id));
      const availableVolumeIds = new Set(nextStructure.volumes.map((volume) => volume.id));

      const nextBranchId =
        (preferred.branchId && availableBranchIds.has(preferred.branchId)
          ? preferred.branchId
          : null) ??
        nextStructure.default_branch_id ??
        nextStructure.branches[0]?.id ??
        null;
      const nextVolumeId =
        (preferred.volumeId && availableVolumeIds.has(preferred.volumeId)
          ? preferred.volumeId
          : null) ??
        nextStructure.default_volume_id ??
        nextStructure.volumes[0]?.id ??
        null;

      setSelectedBranchId(nextBranchId);
      setSelectedVolumeId(nextVolumeId);
      setBranchSourceId((current) => {
        if (current && availableBranchIds.has(current)) {
          return current;
        }
        return nextBranchId ?? "";
      });
    },
    [],
  );

  const loadStructure = useCallback(
    async (preferred: Partial<StructureSelection> = {}) => {
      setLoadingStructure(true);
      setError(null);
      try {
        const data = await apiFetchWithAuth<ProjectStructure>(
          `/api/v1/projects/${projectId}/structure`,
        );
        applyStructure(data, preferred);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to load project structure.",
        );
      } finally {
        setLoadingStructure(false);
      }
    },
    [applyStructure, projectId],
  );

  const loadChapters = useCallback(
    async (branchId: string | null, volumeId: string | null) => {
      if (!branchId || !volumeId) {
        setChapters([]);
        setChapterNumber(1);
        return;
      }

      setLoadingChapters(true);
      setError(null);
      try {
        const query = new URLSearchParams({
          branch_id: branchId,
          volume_id: volumeId,
        });
        const chapterData = await apiFetchWithAuth<Chapter[]>(
          `/api/v1/projects/${projectId}/chapters?${query.toString()}`,
        );
        setChapters(chapterData);
        const lastChapter = chapterData[chapterData.length - 1];
        setChapterNumber((lastChapter?.chapter_number ?? 0) + 1);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Failed to load chapters.",
        );
      } finally {
        setLoadingChapters(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    void loadStructure();
  }, [loadStructure]);

  useEffect(() => {
    if (!selectedBranchId || !selectedVolumeId) {
      return;
    }
    void loadChapters(selectedBranchId, selectedVolumeId);
  }, [loadChapters, selectedBranchId, selectedVolumeId]);

  const project = structure?.project ?? null;
  const canEditProject =
    project?.access_role === "owner" || project?.access_role === "editor";
  const selectedBranch =
    structure?.branches.find((branch) => branch.id === selectedBranchId) ?? null;
  const selectedVolume =
    structure?.volumes.find((volume) => volume.id === selectedVolumeId) ?? null;

  async function handleCreateChapter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBranchId || !selectedVolumeId) {
      setError("请选择分支和卷后再创建章节。");
      return;
    }

    setCreatingChapter(true);
    setError(null);
    try {
      const chapter = await apiFetchWithAuth<Chapter>(
        `/api/v1/projects/${projectId}/chapters`,
        {
          method: "POST",
          body: JSON.stringify({
            chapter_number: chapterNumber,
            branch_id: selectedBranchId,
            volume_id: selectedVolumeId,
            title: title || null,
            content: "",
            status: "draft",
            change_reason: "Created from chapters workspace",
          }),
        },
      );
      const nextChapters = [...chapters, chapter].sort(
        (left, right) => left.chapter_number - right.chapter_number,
      );
      setChapters(nextChapters);
      setTitle("");
      setChapterNumber((nextChapters[nextChapters.length - 1]?.chapter_number ?? 0) + 1);
      setStructure((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          volumes: current.volumes.map((volume) =>
            volume.id === selectedVolumeId
              ? { ...volume, chapter_count: volume.chapter_count + 1 }
              : volume,
          ),
          branches: current.branches.map((branch) =>
            branch.id === selectedBranchId
              ? { ...branch, chapter_count: branch.chapter_count + 1 }
              : branch,
          ),
        };
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to create chapter.",
      );
    } finally {
      setCreatingChapter(false);
    }
  }

  async function handleCreateVolume(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreatingVolume(true);
    setError(null);
    try {
      const previous = structure;
      const nextStructure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/volumes`,
        {
          method: "POST",
          body: JSON.stringify({
            title: volumeTitle.trim(),
            summary: volumeSummary || null,
            status: "planning",
          }),
        },
      );
      const newVolume =
        nextStructure.volumes.find(
          (volume) => !previous?.volumes.some((item) => item.id === volume.id),
        ) ?? nextStructure.volumes[nextStructure.volumes.length - 1];
      applyStructure(nextStructure, {
        branchId: selectedBranchId,
        volumeId: newVolume?.id ?? selectedVolumeId,
      });
      setVolumeTitle("");
      setVolumeSummary("");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to create volume.",
      );
    } finally {
      setCreatingVolume(false);
    }
  }

  async function handleCreateBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreatingBranch(true);
    setError(null);
    try {
      const previous = structure;
      const nextStructure = await apiFetchWithAuth<ProjectStructure>(
        `/api/v1/projects/${projectId}/branches`,
        {
          method: "POST",
          body: JSON.stringify({
            title: branchTitle.trim(),
            key: branchKey.trim() || null,
            description: branchDescription || null,
            status: "active",
            source_branch_id: branchSourceId || null,
            copy_chapters: branchCopyChapters,
            is_default: branchAsDefault,
          }),
        },
      );
      const newBranch =
        nextStructure.branches.find(
          (branch) => !previous?.branches.some((item) => item.id === branch.id),
        ) ?? nextStructure.branches[nextStructure.branches.length - 1];
      applyStructure(nextStructure, {
        branchId: newBranch?.id ?? selectedBranchId,
        volumeId: selectedVolumeId,
      });
      setBranchTitle("");
      setBranchKey("");
      setBranchDescription("");
      setBranchCopyChapters(true);
      setBranchAsDefault(false);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to create branch.",
      );
    } finally {
      setCreatingBranch(false);
    }
  }

  async function handleExportProject(format: "md" | "txt") {
    setExportingFormat(format);
    setError(null);
    try {
      await downloadWithAuth(`/api/v1/projects/${projectId}/export?format=${format}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to export project.",
      );
    } finally {
      setExportingFormat(null);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="rounded-[2rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,250,242,0.96),rgba(245,237,227,0.92))] p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Chapters Workspace
              </p>
              <h1 className="mt-3 text-4xl font-semibold">
                {project?.title ?? "章节结构工作区"}
              </h1>
              <p className="mt-3 text-sm leading-7 text-black/65">
                这里不再只管理章节列表，而是直接管理卷结构、分支结构和当前写作视图。章节创建、导出和编辑都会跟随当前结构上下文。
              </p>
              {project ? (
                <p className="mt-3 text-sm leading-7 text-black/55">
                  当前角色：{project.access_role}
                  {project.owner_email ? ` · Owner ${project.owner_email}` : ""}
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
                href={`/dashboard/projects/${projectId}/bible`}
              >
                Story Bible
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/collaborators`}
              >
                协作者
              </Link>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleExportProject("md")}
                disabled={exportingFormat === "md"}
              >
                {exportingFormat === "md" ? "导出中..." : "导出项目 MD"}
              </button>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleExportProject("txt")}
                disabled={exportingFormat === "txt"}
              >
                {exportingFormat === "txt" ? "导出中..." : "导出项目 TXT"}
              </button>
            </div>
          </div>
        </section>

        {error ? (
          <div className="rounded-3xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex flex-col gap-6">
            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">当前结构视图</h2>
                  <p className="mt-2 text-sm text-black/65">
                    选定一个分支和卷，后续章节列表、创建入口和导出上下文都会跟着切换。
                  </p>
                </div>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                  type="button"
                  onClick={() =>
                    void loadStructure({
                      branchId: selectedBranchId,
                      volumeId: selectedVolumeId,
                    })
                  }
                >
                  刷新结构
                </button>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-2 text-sm">
                  分支
                  <select
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={selectedBranchId ?? ""}
                    onChange={(event) => setSelectedBranchId(event.target.value || null)}
                    disabled={loadingStructure}
                  >
                    {structure?.branches.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.title}
                        {branch.is_default ? " · 默认" : ""}
                        {` · ${branch.chapter_count} 章`}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-2 text-sm">
                  卷
                  <select
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={selectedVolumeId ?? ""}
                    onChange={(event) => setSelectedVolumeId(event.target.value || null)}
                    disabled={loadingStructure}
                  >
                    {structure?.volumes.map((volume) => (
                      <option key={volume.id} value={volume.id}>
                        {`第 ${volume.volume_number} 卷 · ${volume.title} · ${volume.chapter_count} 章`}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <article className="rounded-2xl border border-black/10 bg-[rgba(248,242,234,0.7)] p-5">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">Branch</p>
                  <h3 className="mt-2 text-lg font-semibold">
                    {selectedBranch?.title ?? "未选择分支"}
                  </h3>
                  <p className="mt-2 text-sm text-black/65">
                    Key：{selectedBranch?.key ?? "main"}
                  </p>
                  <p className="mt-1 text-sm text-black/65">
                    章节数：{selectedBranch?.chapter_count ?? 0}
                  </p>
                  {selectedBranch?.description ? (
                    <p className="mt-3 text-sm leading-7 text-black/65">
                      {selectedBranch.description}
                    </p>
                  ) : null}
                </article>

                <article className="rounded-2xl border border-black/10 bg-[rgba(246,245,239,0.84)] p-5">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">Volume</p>
                  <h3 className="mt-2 text-lg font-semibold">
                    {selectedVolume
                      ? `第 ${selectedVolume.volume_number} 卷 · ${selectedVolume.title}`
                      : "未选择卷"}
                  </h3>
                  <p className="mt-2 text-sm text-black/65">
                    章节数：{selectedVolume?.chapter_count ?? 0}
                  </p>
                  {selectedVolume?.summary ? (
                    <p className="mt-3 text-sm leading-7 text-black/65">
                      {selectedVolume.summary}
                    </p>
                  ) : null}
                </article>
              </div>
            </section>

            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">章节列表</h2>
                  <p className="mt-2 text-sm text-black/65">
                    当前显示 {selectedBranch?.title ?? "当前分支"} /{" "}
                    {selectedVolume?.title ?? "当前卷"} 下的章节。
                  </p>
                </div>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                  type="button"
                  onClick={() => void loadChapters(selectedBranchId, selectedVolumeId)}
                >
                  刷新章节
                </button>
              </div>

              {loadingStructure || loadingChapters ? (
                <p className="mt-6 text-sm text-black/65">加载工作区中...</p>
              ) : null}

              {!loadingStructure && !loadingChapters && chapters.length === 0 ? (
                <p className="mt-6 text-sm leading-7 text-black/65">
                  当前结构下还没有章节。先创建一章，后续就可以按这个卷和分支继续生成、编辑和导出。
                </p>
              ) : null}

              <div className="mt-6 grid gap-4">
                {chapters.map((chapter) => (
                  <article
                    key={chapter.id}
                    className="rounded-2xl border border-black/10 bg-white/85 p-5"
                  >
                    {chapter.pending_checkpoint_count > 0 ||
                    chapter.rejected_checkpoint_count > 0 ||
                    chapter.latest_checkpoint_title ||
                    chapter.review_gate_blocked ? (
                      <div
                        className={`mb-4 rounded-2xl border px-4 py-3 text-sm ${finalGateTone(
                          chapter.final_gate_status,
                        )}`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-current/20 px-2 py-1 text-[11px] uppercase tracking-[0.14em]">
                            {formatFinalGateStatus(chapter.final_gate_status)}
                          </span>
                          <span>
                            待处理 {chapter.pending_checkpoint_count} · 驳回{" "}
                            {chapter.rejected_checkpoint_count}
                          </span>
                        </div>
                        {chapter.final_gate_reason ? (
                          <p className="mt-2 leading-6">{chapter.final_gate_reason}</p>
                        ) : null}
                        {chapter.latest_checkpoint_title ? (
                          <p className="mt-1 leading-6">
                            最近 checkpoint：{chapter.latest_checkpoint_title}
                            {chapter.latest_checkpoint_status
                              ? ` · ${chapter.latest_checkpoint_status}`
                              : ""}
                          </p>
                        ) : null}
                        {chapter.latest_review_verdict ? (
                          <p className="mt-1 leading-6">
                            最新审阅：{formatReviewVerdict(chapter.latest_review_verdict)}
                            {chapter.latest_review_summary
                              ? ` · ${chapter.latest_review_summary}`
                              : ""}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-copper">
                          Chapter {chapter.chapter_number}
                        </p>
                        <h3 className="mt-2 text-lg font-semibold">
                          {chapter.title || `第 ${chapter.chapter_number} 章`}
                        </h3>
                        <p className="mt-2 text-sm text-black/65">
                          状态：{chapter.status}
                        </p>
                        <p className="mt-1 text-sm text-black/65">
                          词数：{chapter.word_count ?? 0}
                        </p>
                      </div>
                      <Link
                        className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                        href={`/dashboard/editor/${chapter.id}`}
                      >
                        打开编辑器
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <div className="flex flex-col gap-6">
            <form
              className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
              onSubmit={handleCreateChapter}
            >
              <h2 className="text-xl font-semibold">创建章节</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                新章节会直接落在当前选中的分支和卷下面。
              </p>
              {!canEditProject ? (
                <p className="mt-3 text-sm leading-7 text-amber-700">
                  当前角色只有查看权限，不能创建或调整章节结构。
                </p>
              ) : null}
              <div className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  章节号
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    type="number"
                    min={1}
                    value={chapterNumber}
                    onChange={(event) =>
                      setChapterNumber(Number(event.target.value) || 1)
                    }
                    disabled={!canEditProject}
                    required
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  标题
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    disabled={!canEditProject}
                  />
                </label>
              </div>

              <button
                className="mt-6 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={
                  creatingChapter ||
                  !canEditProject ||
                  !selectedBranchId ||
                  !selectedVolumeId ||
                  loadingStructure
                }
              >
                {creatingChapter ? "创建中..." : "创建章节"}
              </button>
            </form>

            <form
              className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
              onSubmit={handleCreateVolume}
            >
              <h2 className="text-xl font-semibold">新建卷</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                新卷默认自动排到末尾，创建后会切换到新卷视图。
              </p>
              <div className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  卷标题
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={volumeTitle}
                    onChange={(event) => setVolumeTitle(event.target.value)}
                    disabled={!canEditProject}
                    required
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  卷摘要
                  <textarea
                    className="min-h-[112px] rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={volumeSummary}
                    onChange={(event) => setVolumeSummary(event.target.value)}
                    disabled={!canEditProject}
                  />
                </label>
              </div>

              <button
                className="mt-6 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={creatingVolume || !canEditProject || !volumeTitle.trim()}
              >
                {creatingVolume ? "创建中..." : "创建新卷"}
              </button>
            </form>

            <form
              className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
              onSubmit={handleCreateBranch}
            >
              <h2 className="text-xl font-semibold">新建分支</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                可基于现有分支复制章节，用来承载支线、平行改写或重构版本。
              </p>
              <div className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  分支标题
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={branchTitle}
                    onChange={(event) => setBranchTitle(event.target.value)}
                    disabled={!canEditProject}
                    required
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  分支 Key
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={branchKey}
                    onChange={(event) => setBranchKey(event.target.value)}
                    disabled={!canEditProject}
                    placeholder="可选，不填则自动生成"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  来源分支
                  <select
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={branchSourceId}
                    onChange={(event) => setBranchSourceId(event.target.value)}
                    disabled={!canEditProject}
                  >
                    <option value="">默认分支</option>
                    {structure?.branches.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  分支说明
                  <textarea
                    className="min-h-[112px] rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={branchDescription}
                    onChange={(event) => setBranchDescription(event.target.value)}
                    disabled={!canEditProject}
                  />
                </label>
              </div>

              <label className="mt-5 flex items-center gap-3 text-sm text-black/70">
                <input
                  className="h-4 w-4 accent-copper"
                  type="checkbox"
                  checked={branchCopyChapters}
                  onChange={(event) => setBranchCopyChapters(event.target.checked)}
                  disabled={!canEditProject}
                />
                创建时复制来源分支章节
              </label>
              <label className="mt-3 flex items-center gap-3 text-sm text-black/70">
                <input
                  className="h-4 w-4 accent-copper"
                  type="checkbox"
                  checked={branchAsDefault}
                  onChange={(event) => setBranchAsDefault(event.target.checked)}
                  disabled={!canEditProject}
                />
                设为默认分支
              </label>

              <button
                className="mt-6 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={creatingBranch || !canEditProject || !branchTitle.trim()}
              >
                {creatingBranch ? "创建中..." : "创建分支"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}
