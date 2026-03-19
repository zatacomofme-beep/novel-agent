"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import type { ProjectCollaboration } from "@/types/api";

const ROLE_OPTIONS = [
  { value: "editor", label: "Editor" },
  { value: "reviewer", label: "Reviewer" },
  { value: "viewer", label: "Viewer" },
] as const;

function roleBadgeClassName(role: string): string {
  if (role === "owner") {
    return "border-copper/20 bg-[#f6ede3] text-copper";
  }
  if (role === "editor") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (role === "reviewer") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  return "border-black/10 bg-white text-black/60";
}

export default function ProjectCollaboratorsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [collaboration, setCollaboration] = useState<ProjectCollaboration | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("editor");
  const [roleDrafts, setRoleDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  const loadCollaboration = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators`,
      );
      setCollaboration(data);
      setRoleDrafts(
        Object.fromEntries(
          data.members
            .filter((member) => !member.is_owner)
            .map((member) => [member.id, member.role]),
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load collaborators.",
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadCollaboration();
  }, [loadCollaboration]);

  const project = collaboration?.project ?? null;
  const canManage = collaboration?.current_role === "owner";

  async function handleAddCollaborator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators`,
        {
          method: "POST",
          body: JSON.stringify({
            email,
            role,
          }),
        },
      );
      setCollaboration(data);
      setRoleDrafts(
        Object.fromEntries(
          data.members
            .filter((member) => !member.is_owner)
            .map((member) => [member.id, member.role]),
        ),
      );
      setEmail("");
      setRole("editor");
      setSuccess("协作者已加入项目。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to add collaborator.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateRole(memberId: string) {
    const nextRole = roleDrafts[memberId];
    if (!nextRole) {
      return;
    }
    setMutatingId(memberId);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators/${memberId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ role: nextRole }),
        },
      );
      setCollaboration(data);
      setSuccess("协作者角色已更新。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to update collaborator role.",
      );
    } finally {
      setMutatingId(null);
    }
  }

  async function handleRemoveCollaborator(memberId: string) {
    setMutatingId(memberId);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators/${memberId}`,
        {
          method: "DELETE",
        },
      );
      setCollaboration(data);
      setRoleDrafts(
        Object.fromEntries(
          data.members
            .filter((member) => !member.is_owner)
            .map((member) => [member.id, member.role]),
        ),
      );
      setSuccess("协作者已移出项目。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to remove collaborator.",
      );
    } finally {
      setMutatingId(null);
    }
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <section className="rounded-[2rem] border border-black/10 bg-[linear-gradient(135deg,rgba(246,244,238,0.98),rgba(238,232,223,0.92))] p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Collaboration
              </p>
              <h1 className="mt-3 text-4xl font-semibold">
                {project?.title ?? "项目协作成员"}
              </h1>
              <p className="mt-3 text-sm leading-7 text-black/65">
                协作能力先落在项目成员和角色控制。Owner 可以按邮箱加入已注册用户，编辑者和审阅者将直接共享同一个项目工作区。
              </p>
              {collaboration ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <span
                    className={`rounded-full border px-3 py-1 text-xs ${roleBadgeClassName(collaboration.current_role)}`}
                  >
                    当前角色 {collaboration.current_role}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    Owner {project?.owner_email ?? "-"}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    协作者 {project?.collaborator_count ?? 0}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href="/dashboard"
              >
                返回工作台
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/quality`}
              >
                质量详情
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/chapters`}
              >
                章节工作区
              </Link>
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

        <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <div className="grid gap-6">
            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <h2 className="text-xl font-semibold">权限说明</h2>
              <div className="mt-6 grid gap-3 text-sm text-black/70">
                <p className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  Owner：管理项目、协作者、结构、Story Bible 和章节。
                </p>
                <p className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  Editor：可编辑 Story Bible、章节、结构，并发起生成。
                </p>
                <p className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  Reviewer：可查看项目并执行评估，不修改正文结构。
                </p>
                <p className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  Viewer：只读查看、导出和趋势浏览。
                </p>
              </div>
            </section>

            <form
              className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
              onSubmit={handleAddCollaborator}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">新增协作者</h2>
                  <p className="mt-2 text-sm leading-7 text-black/65">
                    目前只支持加入已注册用户，输入邮箱即可直接授权进入这个项目。
                  </p>
                </div>
                <span
                  className={`rounded-full border px-3 py-1 text-xs ${roleBadgeClassName(
                    collaboration?.current_role ?? "viewer",
                  )}`}
                >
                  {canManage ? "可管理" : "只读"}
                </span>
              </div>

              <div className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  用户邮箱
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    disabled={!canManage || submitting}
                    required
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm">
                  角色
                  <select
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                    disabled={!canManage || submitting}
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <button
                className="mt-6 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={!canManage || submitting || !email.trim()}
              >
                {submitting ? "添加中..." : "添加协作者"}
              </button>
            </form>
          </div>

          <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">成员列表</h2>
                <p className="mt-2 text-sm leading-7 text-black/65">
                  所有协作者都会共享同一个项目上下文。角色变化后立即生效。
                </p>
              </div>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                type="button"
                onClick={() => void loadCollaboration()}
              >
                刷新
              </button>
            </div>

            {loading ? (
              <p className="mt-6 text-sm text-black/60">加载协作者中...</p>
            ) : null}

            {!loading && (collaboration?.members.length ?? 0) === 0 ? (
              <p className="mt-6 text-sm leading-7 text-black/60">
                当前还没有成员数据。
              </p>
            ) : null}

            <div className="mt-6 grid gap-4">
              {(collaboration?.members ?? []).map((member) => (
                <article
                  key={member.id}
                  className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${roleBadgeClassName(
                            member.role,
                          )}`}
                        >
                          {member.role}
                        </span>
                        {member.is_owner ? (
                          <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper">
                            Owner
                          </span>
                        ) : null}
                      </div>
                      <h3 className="mt-3 text-lg font-semibold">{member.email}</h3>
                    </div>

                    {!member.is_owner ? (
                      <div className="flex flex-wrap gap-2">
                        <select
                          className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm outline-none transition focus:border-copper"
                          value={roleDrafts[member.id] ?? member.role}
                          onChange={(event) =>
                            setRoleDrafts((current) => ({
                              ...current,
                              [member.id]: event.target.value,
                            }))
                          }
                          disabled={!canManage || mutatingId === member.id}
                        >
                          {ROLE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                          type="button"
                          onClick={() => void handleUpdateRole(member.id)}
                          disabled={!canManage || mutatingId === member.id}
                        >
                          保存角色
                        </button>
                        <button
                          className="rounded-2xl border border-red-200 bg-white px-4 py-2 text-sm text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                          type="button"
                          onClick={() => void handleRemoveCollaborator(member.id)}
                          disabled={!canManage || mutatingId === member.id}
                        >
                          移除
                        </button>
                      </div>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
