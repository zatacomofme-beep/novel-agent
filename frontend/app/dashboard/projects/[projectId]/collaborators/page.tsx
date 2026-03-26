"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import type { ProjectCollaboration, ProjectCollaborator } from "@/types/api";

type CollaboratorsPageProps = {
  params: {
    projectId: string;
  };
};

const ROLE_LABELS: Record<string, string> = {
  owner: "所有者",
  editor: "共写",
  reviewer: "审稿",
  viewer: "只读",
};

const ROLE_HINTS: Record<string, string> = {
  owner: "可管理项目、成员、设定与正文",
  editor: "可写正文、改设定、跑流程",
  reviewer: "可查看项目并做复核与评估",
  viewer: "只能查看，不改正文与设定",
};

const ROLE_TONES: Record<string, string> = {
  owner: "border-copper/20 bg-[#fbf3e8] text-copper",
  editor: "border-emerald-200 bg-emerald-50 text-emerald-700",
  reviewer: "border-sky-200 bg-sky-50 text-sky-700",
  viewer: "border-black/10 bg-[#fbfaf5] text-black/60",
};

const COLLABORATOR_ROLE_OPTIONS = [
  { value: "editor", label: "共写" },
  { value: "reviewer", label: "审稿" },
  { value: "viewer", label: "只读" },
] as const;

function formatRoleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

function formatRoleHint(role: string): string {
  return ROLE_HINTS[role] ?? "按项目权限参与协作。";
}

function roleTone(role: string): string {
  return ROLE_TONES[role] ?? ROLE_TONES.viewer;
}

export default function CollaboratorsPage({ params }: CollaboratorsPageProps) {
  const projectId = params.projectId;
  const [collaboration, setCollaboration] = useState<ProjectCollaboration | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("editor");
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const ownerMember = useMemo(
    () => collaboration?.members.find((member) => member.is_owner) ?? null,
    [collaboration?.members],
  );
  const collaboratorMembers = useMemo(
    () => collaboration?.members.filter((member) => !member.is_owner) ?? [],
    [collaboration?.members],
  );
  const canManage = collaboration?.current_role === "owner";

  const loadCollaboration = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators`,
      );
      setCollaboration(data);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadCollaboration();
  }, [loadCollaboration]);

  async function handleInvite() {
    if (!inviteEmail.trim()) {
      return;
    }

    setActionKey("invite");
    setError(null);
    setSuccess(null);

    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators`,
        {
          method: "POST",
          body: JSON.stringify({
            email: inviteEmail.trim(),
            role: inviteRole,
          }),
        },
      );
      setCollaboration(data);
      setInviteEmail("");
      setInviteRole("editor");
      setSuccess("协作者已经加入这本书。");
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setActionKey(null);
    }
  }

  async function handleChangeRole(member: ProjectCollaborator, nextRole: string) {
    if (member.is_owner || member.role === nextRole) {
      return;
    }

    setActionKey(`role:${member.id}`);
    setError(null);
    setSuccess(null);

    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators/${member.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            role: nextRole,
          }),
        },
      );
      setCollaboration(data);
      setSuccess(`已把 ${member.email} 调整为${formatRoleLabel(nextRole)}。`);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setActionKey(null);
    }
  }

  async function handleRemove(member: ProjectCollaborator) {
    const confirmed = window.confirm(`确认移除 ${member.email} 吗？`);
    if (!confirmed) {
      return;
    }

    setActionKey(`remove:${member.id}`);
    setError(null);
    setSuccess(null);

    try {
      const data = await apiFetchWithAuth<ProjectCollaboration>(
        `/api/v1/projects/${projectId}/collaborators/${member.id}`,
        {
          method: "DELETE",
        },
      );
      setCollaboration(data);
      setSuccess(`${member.email} 已从这本书移除。`);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      setActionKey(null);
    }
  }

  return (
    <main className="min-h-screen px-4 py-8 md:px-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <section className="rounded-[38px] border border-black/10 bg-white/80 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)] md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">协作成员</p>
              <h1 className="mt-2 text-3xl font-semibold">
                {collaboration?.project.title ?? "项目协作"}
              </h1>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  你的身份 {formatRoleLabel(collaboration?.current_role ?? "viewer")}
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  共 {collaboration?.members.length ?? 0} 人
                </span>
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                  协作者 {collaboration?.project.collaborator_count ?? 0} 人
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href={`/dashboard/projects/${projectId}/story-room`}
              >
                回故事工作台
              </Link>
              <Link
                className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/dashboard"
              >
                返回项目总览
              </Link>
            </div>
          </div>

          {error ? (
            <div className="mt-5 rounded-3xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="mt-5 rounded-3xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {success}
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(ROLE_LABELS).map(([role, label]) => (
              <article
                key={role}
                className={`rounded-[24px] border px-4 py-4 ${roleTone(role)}`}
              >
                <p className="text-sm font-semibold">{label}</p>
                <p className="mt-2 text-xs leading-6 opacity-80">{formatRoleHint(role)}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
          <section className="rounded-[34px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-copper">邀请</p>
                <h2 className="mt-2 text-2xl font-semibold">把人加进来</h2>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs ${
                  canManage
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-black/10 bg-[#fbfaf5] text-black/55"
                }`}
              >
                {canManage ? "可管理" : "仅查看"}
              </span>
            </div>

            {canManage ? (
              <div className="mt-6 space-y-4">
                <label className="block">
                  <span className="text-sm text-black/60">协作者邮箱</span>
                  <input
                    className="mt-2 w-full rounded-[20px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                    value={inviteEmail}
                    onChange={(event) => setInviteEmail(event.target.value)}
                    placeholder="输入已注册账号的邮箱"
                  />
                </label>

                <label className="block">
                  <span className="text-sm text-black/60">协作身份</span>
                  <select
                    className="mt-2 w-full rounded-[20px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                    value={inviteRole}
                    onChange={(event) => setInviteRole(event.target.value)}
                  >
                    {COLLABORATOR_ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4 text-sm leading-7 text-black/62">
                  新加入的人会立刻获得这本书的访问权限，不需要离开前台再单独配置。
                </div>

                <button
                  className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!inviteEmail.trim() || actionKey === "invite"}
                  onClick={() => void handleInvite()}
                  type="button"
                >
                  {actionKey === "invite" ? "邀请中..." : "邀请加入"}
                </button>
              </div>
            ) : (
              <div className="mt-6 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-4 text-sm leading-7 text-black/62">
                当前身份只能查看成员列表。需要项目所有者来邀请、调整角色或移除成员。
              </div>
            )}
          </section>

          <section className="rounded-[34px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-copper">成员</p>
                <h2 className="mt-2 text-2xl font-semibold">谁在这本书里</h2>
              </div>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={() => void loadCollaboration()}
                type="button"
              >
                刷新
              </button>
            </div>

            {loading ? (
              <div className="mt-6 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-6 text-sm text-black/55">
                正在装载成员列表...
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                {ownerMember ? (
                  <article className="rounded-[26px] border border-copper/15 bg-[#fbf3e8] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-black/82">{ownerMember.email}</p>
                        <p className="mt-2 text-xs leading-6 text-black/58">项目所有者，拥有全部权限。</p>
                      </div>
                      <span className="rounded-full border border-copper/20 bg-white px-3 py-1 text-xs text-copper">
                        所有者
                      </span>
                    </div>
                  </article>
                ) : null}

                {collaboratorMembers.length > 0 ? (
                  collaboratorMembers.map((member) => (
                    <article
                      key={member.id}
                      className="rounded-[26px] border border-black/10 bg-[#fbfaf5] p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-black/82">{member.email}</p>
                          <p className="mt-2 text-xs leading-6 text-black/58">
                            {formatRoleHint(member.role)}
                          </p>
                        </div>

                        {canManage ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 outline-none disabled:cursor-not-allowed disabled:opacity-60"
                              value={member.role}
                              disabled={actionKey === `role:${member.id}` || actionKey === `remove:${member.id}`}
                              onChange={(event) => void handleChangeRole(member, event.target.value)}
                            >
                              {COLLABORATOR_ROLE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                            <button
                              className="rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={actionKey === `remove:${member.id}` || actionKey === `role:${member.id}`}
                              onClick={() => void handleRemove(member)}
                              type="button"
                            >
                              {actionKey === `remove:${member.id}` ? "移除中..." : "移除"}
                            </button>
                          </div>
                        ) : (
                          <span className={`rounded-full border px-3 py-1 text-xs ${roleTone(member.role)}`}>
                            {formatRoleLabel(member.role)}
                          </span>
                        )}
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[24px] border border-dashed border-black/10 bg-[#fbfaf5] px-4 py-6 text-sm text-black/52">
                    现在还没有其他协作者，这本书目前只有你自己在写。
                  </div>
                )}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}
