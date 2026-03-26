"use client";

import { useEffect, useMemo, useState } from "react";

import type { Chapter, ProjectBranch, ProjectVolume } from "@/types/api";

type StoryScopeSwitcherProps = {
  branches: ProjectBranch[];
  volumes: ProjectVolume[];
  selectedBranchId: string | null;
  selectedVolumeId: string | null;
  chapterCount: number;
  pendingChangeCount: number;
  scopeChapters: Chapter[];
  activeChapterNumber: number;
  actionKey: string | null;
  onSelectBranchId: (branchId: string) => void;
  onSelectVolumeId: (volumeId: string) => void;
  onJumpToChapter: (chapterNumber: number) => void;
  onCreateBranch: (payload: {
    title: string;
    description: string | null;
    sourceBranchId: string | null;
    copyChapters: boolean;
    isDefault: boolean;
  }) => Promise<boolean>;
  onUpdateBranch: (branchId: string, payload: {
    title: string;
    description: string | null;
    isDefault: boolean;
  }) => Promise<boolean>;
  onCreateVolume: (payload: {
    volumeNumber: number | null;
    title: string;
    summary: string | null;
  }) => Promise<boolean>;
  onUpdateVolume: (volumeId: string, payload: {
    volumeNumber: number | null;
    title: string;
    summary: string | null;
  }) => Promise<boolean>;
};

type BranchFormMode = "create" | "edit" | null;
type VolumeFormMode = "create" | "edit" | null;

function formatBranchBadge(branch: ProjectBranch | undefined): string | null {
  if (!branch) {
    return null;
  }
  if (branch.is_default) {
    return "主线";
  }
  if (branch.source_branch_id) {
    return "支线";
  }
  return "分线";
}

function nextVolumeNumber(volumes: ProjectVolume[]): number {
  return Math.max(...volumes.map((item) => item.volume_number), 0) + 1;
}

export function StoryScopeSwitcher({
  branches,
  volumes,
  selectedBranchId,
  selectedVolumeId,
  chapterCount,
  pendingChangeCount,
  scopeChapters,
  activeChapterNumber,
  actionKey,
  onSelectBranchId,
  onSelectVolumeId,
  onJumpToChapter,
  onCreateBranch,
  onUpdateBranch,
  onCreateVolume,
  onUpdateVolume,
}: StoryScopeSwitcherProps) {
  const [branchFormMode, setBranchFormMode] = useState<BranchFormMode>(null);
  const [volumeFormMode, setVolumeFormMode] = useState<VolumeFormMode>(null);
  const [branchTitle, setBranchTitle] = useState("");
  const [branchDescription, setBranchDescription] = useState("");
  const [branchSourceId, setBranchSourceId] = useState<string>("");
  const [branchCopyChapters, setBranchCopyChapters] = useState(true);
  const [branchIsDefault, setBranchIsDefault] = useState(false);
  const [volumeTitle, setVolumeTitle] = useState("");
  const [volumeSummary, setVolumeSummary] = useState("");
  const [volumeNumber, setVolumeNumber] = useState("");

  const selectedBranch = branches.find((item) => item.id === selectedBranchId);
  const selectedVolume = volumes.find((item) => item.id === selectedVolumeId);
  const branchBadge = formatBranchBadge(selectedBranch);
  const branchSource = branches.find((item) => item.id === selectedBranch?.source_branch_id) ?? null;
  const nextVolume = useMemo(() => nextVolumeNumber(volumes), [volumes]);

  useEffect(() => {
    if (branchFormMode === "create") {
      setBranchTitle("");
      setBranchDescription("");
      setBranchSourceId(selectedBranchId ?? branches[0]?.id ?? "");
      setBranchCopyChapters(true);
      setBranchIsDefault(false);
      return;
    }
    if (branchFormMode === "edit" && selectedBranch) {
      setBranchTitle(selectedBranch.title);
      setBranchDescription(selectedBranch.description ?? "");
      setBranchSourceId(selectedBranch.source_branch_id ?? "");
      setBranchCopyChapters(false);
      setBranchIsDefault(selectedBranch.is_default);
    }
  }, [branchFormMode, branches, selectedBranch, selectedBranchId]);

  useEffect(() => {
    if (volumeFormMode === "create") {
      setVolumeTitle("");
      setVolumeSummary("");
      setVolumeNumber(String(nextVolume));
      return;
    }
    if (volumeFormMode === "edit" && selectedVolume) {
      setVolumeTitle(selectedVolume.title);
      setVolumeSummary(selectedVolume.summary ?? "");
      setVolumeNumber(String(selectedVolume.volume_number));
    }
  }, [nextVolume, selectedVolume, volumeFormMode]);

  function isBusy(keyPrefix: string): boolean {
    return actionKey?.startsWith(keyPrefix) ?? false;
  }

  async function handleSubmitBranch() {
    if (!branchTitle.trim()) {
      return;
    }
    if (branchFormMode === "create") {
      const success = await onCreateBranch({
        title: branchTitle.trim(),
        description: branchDescription.trim() || null,
        sourceBranchId: branchSourceId || null,
        copyChapters: branchCopyChapters,
        isDefault: branchIsDefault,
      });
      if (success) {
        setBranchFormMode(null);
      }
      return;
    }
    if (branchFormMode === "edit" && selectedBranch) {
      const success = await onUpdateBranch(selectedBranch.id, {
        title: branchTitle.trim(),
        description: branchDescription.trim() || null,
        isDefault: branchIsDefault,
      });
      if (success) {
        setBranchFormMode(null);
      }
    }
  }

  async function handleSubmitVolume() {
    if (!volumeTitle.trim()) {
      return;
    }
    const parsedVolumeNumber = Number(volumeNumber);
    const normalizedVolumeNumber =
      Number.isFinite(parsedVolumeNumber) && parsedVolumeNumber > 0
        ? Math.round(parsedVolumeNumber)
        : null;

    if (volumeFormMode === "create") {
      const success = await onCreateVolume({
        volumeNumber: normalizedVolumeNumber,
        title: volumeTitle.trim(),
        summary: volumeSummary.trim() || null,
      });
      if (success) {
        setVolumeFormMode(null);
      }
      return;
    }

    if (volumeFormMode === "edit" && selectedVolume) {
      const success = await onUpdateVolume(selectedVolume.id, {
        volumeNumber: normalizedVolumeNumber,
        title: volumeTitle.trim(),
        summary: volumeSummary.trim() || null,
      });
      if (success) {
        setVolumeFormMode(null);
      }
    }
  }

  return (
    <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">卷线工作区</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {branchBadge ? (
              <span className="rounded-full border border-copper/20 bg-white px-3 py-1 text-xs text-copper">
                {branchBadge}
              </span>
            ) : null}
            <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
              当前范围 {chapterCount} 章
            </span>
            <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
              待确认 {pendingChangeCount} 条
            </span>
          </div>
        </div>

        <div className="min-w-[240px] text-right">
          <p className="text-lg font-semibold text-black/84">
            {selectedBranch?.title ?? "未选分线"}
          </p>
          <p className="mt-1 text-sm text-black/52">
            {selectedVolume ? `第 ${selectedVolume.volume_number} 卷 · ${selectedVolume.title}` : "未选卷"}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <section className="rounded-[24px] border border-black/10 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-black/82">分线</p>
              <p className="mt-1 text-xs text-black/48">切换这里，会一起切换这条线的大纲、正文和设定。</p>
            </div>
            <button
              className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
              onClick={() => setBranchFormMode((current) => (current === "create" ? null : "create"))}
              type="button"
            >
              {branchFormMode === "create" ? "收起" : "新建分线"}
            </button>
          </div>

          <div className="mt-4 grid gap-3">
            {branches.map((branch) => {
              const isActive = branch.id === selectedBranchId;
              const badge = formatBranchBadge(branch);
              return (
                <button
                  key={branch.id}
                  className={`rounded-[22px] border px-4 py-4 text-left transition ${
                    isActive
                      ? "border-copper/25 bg-[#fbf3e8] shadow-[0_14px_30px_rgba(176,112,53,0.1)]"
                      : "border-black/10 bg-[#fbfaf5] hover:bg-white"
                  }`}
                  onClick={() => onSelectBranchId(branch.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-black/82">{branch.title}</p>
                        {badge ? (
                          <span className="rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] text-black/55">
                            {badge}
                          </span>
                        ) : null}
                      </div>
                      {branch.description ? (
                        <p className="mt-2 text-xs leading-6 text-black/56">{branch.description}</p>
                      ) : null}
                      {branch.source_branch_id ? (
                        <p className="mt-2 text-[11px] text-black/45">
                          来源：{branches.find((item) => item.id === branch.source_branch_id)?.title ?? "原分线"}
                        </p>
                      ) : null}
                    </div>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                      {branch.chapter_count} 章
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {selectedBranch ? (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={() => setBranchFormMode((current) => (current === "edit" ? null : "edit"))}
                type="button"
              >
                {branchFormMode === "edit" ? "收起编辑" : "编辑当前分线"}
              </button>
              {branchSource ? (
                <span className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/55">
                  从 {branchSource.title} 分出来
                </span>
              ) : null}
            </div>
          ) : null}

          {branchFormMode ? (
            <div className="mt-4 rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
              <div className="grid gap-4">
                <label className="block">
                  <span className="text-sm text-black/60">分线名称</span>
                  <input
                    className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                    value={branchTitle}
                    onChange={(event) => setBranchTitle(event.target.value)}
                    placeholder="比如：黑化线 / 宫变支线"
                  />
                </label>

                <label className="block">
                  <span className="text-sm text-black/60">分线说明</span>
                  <textarea
                    className="mt-2 min-h-[96px] w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                    value={branchDescription}
                    onChange={(event) => setBranchDescription(event.target.value)}
                    placeholder="这条线主要改什么。"
                  />
                </label>

                {branchFormMode === "create" ? (
                  <>
                    <label className="block">
                      <span className="text-sm text-black/60">从哪条线开出去</span>
                      <select
                        className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                        value={branchSourceId}
                        onChange={(event) => setBranchSourceId(event.target.value)}
                      >
                        <option value="">不继承现有分线</option>
                        {branches.map((branch) => (
                          <option key={branch.id} value={branch.id}>
                            {branch.title}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="flex items-center gap-3 rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm text-black/68">
                      <input
                        checked={branchCopyChapters}
                        className="h-4 w-4"
                        onChange={(event) => setBranchCopyChapters(event.target.checked)}
                        type="checkbox"
                      />
                      带上当前分线的章节副本
                    </label>
                  </>
                ) : null}

                <label className="flex items-center gap-3 rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm text-black/68">
                  <input
                    checked={branchIsDefault}
                    className="h-4 w-4"
                    onChange={(event) => setBranchIsDefault(event.target.checked)}
                    type="checkbox"
                  />
                  设为默认主线
                </label>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!branchTitle.trim() || isBusy("scope:branch")}
                  onClick={() => void handleSubmitBranch()}
                  type="button"
                >
                  {isBusy("scope:branch")
                    ? "保存中..."
                    : branchFormMode === "create"
                      ? "创建分线"
                      : "保存分线"}
                </button>
                <button
                  className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                  onClick={() => setBranchFormMode(null)}
                  type="button"
                >
                  取消
                </button>
              </div>
            </div>
          ) : null}
        </section>

        <section className="rounded-[24px] border border-black/10 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-black/82">卷</p>
              <p className="mt-1 text-xs text-black/48">切换这里，会切换这条线下正在看的章节范围。</p>
            </div>
            <button
              className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
              onClick={() => setVolumeFormMode((current) => (current === "create" ? null : "create"))}
              type="button"
            >
              {volumeFormMode === "create" ? "收起" : "新建卷"}
            </button>
          </div>

          <div className="mt-4 grid gap-3">
            {volumes.map((volume) => {
              const isActive = volume.id === selectedVolumeId;
              return (
                <button
                  key={volume.id}
                  className={`rounded-[22px] border px-4 py-4 text-left transition ${
                    isActive
                      ? "border-copper/25 bg-[#fbf3e8] shadow-[0_14px_30px_rgba(176,112,53,0.1)]"
                      : "border-black/10 bg-[#fbfaf5] hover:bg-white"
                  }`}
                  onClick={() => onSelectVolumeId(volume.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-black/82">
                          第 {volume.volume_number} 卷 · {volume.title}
                        </p>
                        {volume.is_default ? (
                          <span className="rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] text-black/55">
                            默认卷
                          </span>
                        ) : null}
                      </div>
                      {volume.summary ? (
                        <p className="mt-2 text-xs leading-6 text-black/56">{volume.summary}</p>
                      ) : null}
                    </div>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                      {volume.chapter_count} 章
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {selectedVolume ? (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={() => setVolumeFormMode((current) => (current === "edit" ? null : "edit"))}
                type="button"
              >
                {volumeFormMode === "edit" ? "收起编辑" : "编辑当前卷"}
              </button>
            </div>
          ) : null}

          {volumeFormMode ? (
            <div className="mt-4 rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
              <div className="grid gap-4">
                <div className="grid gap-4 md:grid-cols-[120px_1fr]">
                  <label className="block">
                    <span className="text-sm text-black/60">卷号</span>
                    <input
                      className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                      inputMode="numeric"
                      value={volumeNumber}
                      onChange={(event) => setVolumeNumber(event.target.value)}
                      placeholder={String(nextVolume)}
                    />
                  </label>

                  <label className="block">
                    <span className="text-sm text-black/60">卷名</span>
                    <input
                      className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                      value={volumeTitle}
                      onChange={(event) => setVolumeTitle(event.target.value)}
                      placeholder="比如：入世卷 / 天墟卷"
                    />
                  </label>
                </div>

                <label className="block">
                  <span className="text-sm text-black/60">这一卷主打什么</span>
                  <textarea
                    className="mt-2 min-h-[96px] w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                    value={volumeSummary}
                    onChange={(event) => setVolumeSummary(event.target.value)}
                    placeholder="写这一卷的主冲突、主目标。"
                  />
                </label>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!volumeTitle.trim() || isBusy("scope:volume")}
                  onClick={() => void handleSubmitVolume()}
                  type="button"
                >
                  {isBusy("scope:volume")
                    ? "保存中..."
                    : volumeFormMode === "create"
                      ? "创建卷"
                      : "保存卷"}
                </button>
                <button
                  className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                  onClick={() => setVolumeFormMode(null)}
                  type="button"
                >
                  取消
                </button>
              </div>
            </div>
          ) : null}
        </section>
      </div>

      <div className="mt-5 rounded-[24px] border border-black/10 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-black/82">当前范围章节</p>
            <p className="mt-1 text-xs text-black/48">
              现在看到的是 {selectedBranch?.title ?? "当前分线"} · {selectedVolume?.title ?? "当前卷"}。
            </p>
          </div>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            共 {scopeChapters.length} 章
          </span>
        </div>

        {scopeChapters.length > 0 ? (
          <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
            {scopeChapters.map((chapter) => {
              const isActive = chapter.chapter_number === activeChapterNumber;
              return (
                <button
                  key={chapter.id}
                  className={`min-w-[144px] rounded-[18px] border px-3 py-3 text-left transition ${
                    isActive
                      ? "border-copper/20 bg-[#fbf3e8] text-black shadow-[0_10px_24px_rgba(176,112,53,0.08)]"
                      : "border-black/10 bg-[#fbfaf5] text-black/70 hover:bg-white"
                  }`}
                  onClick={() => onJumpToChapter(chapter.chapter_number)}
                  type="button"
                >
                  <p className="text-xs uppercase tracking-[0.14em] text-black/42">
                    第 {chapter.chapter_number} 章
                  </p>
                  <p className="mt-1 line-clamp-1 text-sm font-semibold">
                    {chapter.title?.trim() || "未命名章节"}
                  </p>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="mt-4 rounded-[20px] border border-dashed border-black/10 bg-[#fbfaf5] px-4 py-5 text-sm text-black/52">
            这条分线在这一卷里还没有章节，可以直接去正文区起这一卷的第一章。
          </div>
        )}
      </div>
    </section>
  );
}
