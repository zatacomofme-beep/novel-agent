"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import { loadAuthSession } from "@/lib/auth";
import type {
  StoryEngineModelOption,
  StoryEngineModelRouting,
  StoryEngineModelRoutingProjectSummary,
  StoryEngineModelRoutingUpdateRequest,
  StoryEngineReasoningEffort,
  StoryEngineRoleRouting,
  User,
} from "@/types/api";

type EditableRoute = {
  model: string;
  reasoning_effort: StoryEngineReasoningEffort | null;
};

type EditableRouteMap = Record<string, EditableRoute>;

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿中",
  active: "创作中",
  archived: "已归档",
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatProjectMeta(summary: StoryEngineModelRoutingProjectSummary): string {
  const parts = [summary.genre, summary.tone].filter(Boolean);
  if (parts.length > 0) {
    return parts.join(" / ");
  }
  return "未填写题材信息";
}

function routesEqual(
  left: EditableRoute | null | undefined,
  right: EditableRoute | null | undefined,
): boolean {
  if (!left || !right) {
    return false;
  }
  return (
    left.model === right.model &&
    (left.reasoning_effort ?? null) === (right.reasoning_effort ?? null)
  );
}

function routeToEditable(route: StoryEngineRoleRouting | undefined): EditableRoute | null {
  if (!route) {
    return null;
  }
  return {
    model: route.model,
    reasoning_effort: route.reasoning_effort ?? null,
  };
}

function mapOverridesToEditable(
  manualOverrides: StoryEngineModelRouting["manual_overrides"] | undefined,
): EditableRouteMap {
  if (!manualOverrides) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(manualOverrides).map(([roleKey, route]) => [
      roleKey,
      {
        model: route.model,
        reasoning_effort: route.reasoning_effort ?? null,
      },
    ]),
  );
}

function overrideMapsEqual(left: EditableRouteMap, right: EditableRouteMap): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }
  return leftKeys.every((roleKey, index) => {
    const compareKey = rightKeys[index];
    return compareKey === roleKey && routesEqual(left[roleKey], right[compareKey]);
  });
}

function buildEffectiveRouting(
  routingData: StoryEngineModelRouting | null,
  activePresetKey: string,
  manualOverrides: EditableRouteMap,
): Record<string, StoryEngineRoleRouting> {
  if (!routingData) {
    return {};
  }

  const preset =
    routingData.presets.find((item) => item.key === activePresetKey) ??
    routingData.presets.find((item) => item.key === routingData.active_preset_key) ??
    routingData.presets[0];

  const baseRouting = preset?.routing ?? {};
  const merged: Record<string, StoryEngineRoleRouting> = {};

  for (const role of routingData.role_catalog) {
    const base = baseRouting[role.role_key] ?? routingData.effective_routing[role.role_key];
    const override = manualOverrides[role.role_key];
    if (!base) {
      continue;
    }
    merged[role.role_key] = {
      ...base,
      model: override?.model ?? base.model,
      reasoning_effort: override?.reasoning_effort ?? base.reasoning_effort ?? null,
      is_override: Boolean(override),
    };
  }

  return merged;
}

function isPermissionError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes("403") || message.includes("权限");
}

function buildAdminHref(projectId?: string | null): string {
  const params = new URLSearchParams();
  if (projectId) {
    params.set("projectId", projectId);
  }
  const query = params.toString();
  return `/dashboard/admin/model-routing${query ? `?${query}` : ""}`;
}

function buildLoginHref(projectId?: string | null): string {
  return `/login?redirect=${encodeURIComponent(buildAdminHref(projectId))}`;
}

function modelNameById(models: StoryEngineModelOption[], modelId: string): string {
  return models.find((item) => item.id === modelId)?.label ?? modelId;
}

function ModelRoutingAdminPageBody() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryProjectId = searchParams.get("projectId");

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [projectSummaries, setProjectSummaries] = useState<
    StoryEngineModelRoutingProjectSummary[]
  >([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [routingData, setRoutingData] = useState<StoryEngineModelRouting | null>(null);
  const [activePresetKey, setActivePresetKey] = useState("");
  const [manualOverrides, setManualOverrides] = useState<EditableRouteMap>({});
  const [queryInput, setQueryInput] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedProjectSummary = useMemo(
    () => projectSummaries.find((item) => item.project_id === selectedProjectId) ?? null,
    [projectSummaries, selectedProjectId],
  );

  const presetMap = useMemo(() => {
    return Object.fromEntries((routingData?.presets ?? []).map((preset) => [preset.key, preset]));
  }, [routingData]);

  const loadedManualOverrides = useMemo(
    () => mapOverridesToEditable(routingData?.manual_overrides),
    [routingData],
  );

  const currentPresetRouting = useMemo(() => {
    return presetMap[activePresetKey]?.routing ?? {};
  }, [activePresetKey, presetMap]);

  const effectiveRouting = useMemo(
    () => buildEffectiveRouting(routingData, activePresetKey, manualOverrides),
    [routingData, activePresetKey, manualOverrides],
  );

  const isDirty = useMemo(() => {
    if (!routingData) {
      return false;
    }
    return (
      activePresetKey !== routingData.active_preset_key ||
      !overrideMapsEqual(manualOverrides, loadedManualOverrides)
    );
  }, [activePresetKey, loadedManualOverrides, manualOverrides, routingData]);

  const loadProjectList = useCallback(
    async (query = "") => {
      setLoadingList(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        if (query.trim()) {
          params.set("query", query.trim());
        }
        params.set("limit", "80");
        const data = await apiFetchWithAuth<StoryEngineModelRoutingProjectSummary[]>(
          `/api/v1/admin/model-routing/projects?${params.toString()}`,
        );
        setProjectSummaries(data);
        setPermissionDenied(false);
      } catch (requestError) {
        setProjectSummaries([]);
        setError(buildUserFriendlyError(requestError));
        if (isPermissionError(requestError)) {
          setPermissionDenied(true);
        }
      } finally {
        setLoadingList(false);
      }
    },
    [],
  );

  const syncDetailState = useCallback((data: StoryEngineModelRouting) => {
    setRoutingData(data);
    setActivePresetKey(data.active_preset_key);
    setManualOverrides(mapOverridesToEditable(data.manual_overrides));
  }, []);

  useEffect(() => {
    const session = loadAuthSession();
    if (!session) {
      setLoadingList(false);
      return;
    }
    setCurrentUser(session.user);
    void loadProjectList();
  }, [loadProjectList]);

  useEffect(() => {
    if (projectSummaries.length === 0) {
      setSelectedProjectId(null);
      setRoutingData(null);
      return;
    }

    const availableIds = new Set(projectSummaries.map((item) => item.project_id));
    if (queryProjectId && availableIds.has(queryProjectId)) {
      if (selectedProjectId !== queryProjectId) {
        setSelectedProjectId(queryProjectId);
      }
      return;
    }

    if (!selectedProjectId || !availableIds.has(selectedProjectId)) {
      setSelectedProjectId(projectSummaries[0].project_id);
    }
  }, [projectSummaries, queryProjectId, selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId || queryProjectId === selectedProjectId) {
      return;
    }
    router.replace(buildAdminHref(selectedProjectId));
  }, [queryProjectId, router, selectedProjectId]);

  useEffect(() => {
    if (!currentUser || !selectedProjectId || permissionDenied) {
      return;
    }

    let cancelled = false;

    async function fetchRoutingDetail() {
      setLoadingDetail(true);
      setError(null);
      setSuccess(null);
      try {
        const data = await apiFetchWithAuth<StoryEngineModelRouting>(
          `/api/v1/admin/model-routing/projects/${selectedProjectId}`,
        );
        if (!cancelled) {
          syncDetailState(data);
          setPermissionDenied(false);
        }
      } catch (requestError) {
        if (cancelled) {
          return;
        }
        setRoutingData(null);
        setError(buildUserFriendlyError(requestError));
        if (isPermissionError(requestError)) {
          setPermissionDenied(true);
        }
      } finally {
        if (!cancelled) {
          setLoadingDetail(false);
        }
      }
    }

    void fetchRoutingDetail();

    return () => {
      cancelled = true;
    };
  }, [currentUser, permissionDenied, selectedProjectId, syncDetailState]);

  function resolveBaseRoute(roleKey: string): EditableRoute | null {
    const route = routeToEditable(currentPresetRouting[roleKey]);
    if (route) {
      return route;
    }
    return routeToEditable(routingData?.effective_routing[roleKey]);
  }

  function handleSelectProject(projectId: string) {
    setSelectedProjectId(projectId);
    setSuccess(null);
  }

  function handlePresetChange(nextPresetKey: string) {
    if (!routingData || !presetMap[nextPresetKey]) {
      return;
    }

    const nextPresetRouting = presetMap[nextPresetKey].routing;
    const nextOverrides: EditableRouteMap = {};

    for (const role of routingData.role_catalog) {
      const currentEffective = routeToEditable(effectiveRouting[role.role_key]);
      const nextBase = routeToEditable(nextPresetRouting[role.role_key]);
      if (currentEffective && nextBase && !routesEqual(currentEffective, nextBase)) {
        nextOverrides[role.role_key] = currentEffective;
      }
    }

    setActivePresetKey(nextPresetKey);
    setManualOverrides(nextOverrides);
    setSuccess(null);
  }

  function handleRoleRouteChange(
    roleKey: string,
    patch: Partial<EditableRoute>,
    selectedModel?: StoryEngineModelOption,
  ) {
    const baseRoute = resolveBaseRoute(roleKey);
    if (!baseRoute) {
      return;
    }

    setManualOverrides((current) => {
      const currentRoute = current[roleKey] ?? baseRoute;
      const nextModel = patch.model ?? currentRoute.model;
      const modelMeta =
        selectedModel ??
        routingData?.available_models.find((item) => item.id === nextModel) ??
        null;
      const nextReasoning =
        modelMeta && !modelMeta.supports_reasoning_effort
          ? null
          : patch.reasoning_effort !== undefined
            ? patch.reasoning_effort
            : currentRoute.reasoning_effort ?? baseRoute.reasoning_effort ?? null;

      const nextRoute: EditableRoute = {
        model: nextModel,
        reasoning_effort: nextReasoning,
      };
      const nextOverrides = { ...current };

      if (routesEqual(baseRoute, nextRoute)) {
        delete nextOverrides[roleKey];
      } else {
        nextOverrides[roleKey] = nextRoute;
      }
      return nextOverrides;
    });
    setSuccess(null);
  }

  function handleResetRole(roleKey: string) {
    setManualOverrides((current) => {
      if (!current[roleKey]) {
        return current;
      }
      const nextOverrides = { ...current };
      delete nextOverrides[roleKey];
      return nextOverrides;
    });
    setSuccess(null);
  }

  function handleClearOverrides() {
    setManualOverrides({});
    setSuccess(null);
  }

  async function handleSave() {
    if (!selectedProjectId || !routingData) {
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: StoryEngineModelRoutingUpdateRequest = {
      active_preset_key: activePresetKey,
      manual_overrides: manualOverrides,
    };

    try {
      const data = await apiFetchWithAuth<StoryEngineModelRouting>(
        `/api/v1/admin/model-routing/projects/${selectedProjectId}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      syncDetailState(data);
      setSuccess("后台策略已经保存。");
      await loadProjectList(queryInput);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
      if (isPermissionError(requestError)) {
        setPermissionDenied(true);
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadProjectList(queryInput);
  }

  if (!currentUser) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_top,#f9f4ea,transparent_45%),linear-gradient(180deg,#f7f1e6_0%,#f3ecde_100%)] px-4 py-10 md:px-6">
        <div className="mx-auto max-w-3xl">
          <section className="rounded-[36px] border border-black/10 bg-white/82 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)]">
            <p className="text-xs uppercase tracking-[0.24em] text-copper">后台策略</p>
            <h1 className="mt-3 text-3xl font-semibold">需要先登录管理员账号</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-black/62">
              这个页面只用于维护不同职责的模型组合，不会出现在写手工作台里。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-paper transition hover:bg-copper"
                href={buildLoginHref(queryProjectId)}
              >
                去登录
              </Link>
              <Link
                className="rounded-full border border-black/10 bg-white px-5 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/"
              >
                返回首页
              </Link>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (permissionDenied) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_top,#f9f4ea,transparent_45%),linear-gradient(180deg,#f7f1e6_0%,#f3ecde_100%)] px-4 py-10 md:px-6">
        <div className="mx-auto max-w-3xl">
          <section className="rounded-[36px] border border-red-200 bg-white/82 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)]">
            <p className="text-xs uppercase tracking-[0.24em] text-copper">后台策略</p>
            <h1 className="mt-3 text-3xl font-semibold">当前账号没有后台权限</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-black/62">
              管理员邮箱白名单由后端环境变量控制。写手账号不会看到这个入口，也不能修改这里的策略。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                className="rounded-full border border-black/10 bg-white px-5 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/dashboard"
              >
                返回项目总览
              </Link>
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#fbf6ee,transparent_38%),linear-gradient(180deg,#f7f0e3_0%,#f2ebde_100%)] px-4 py-8 md:px-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="overflow-hidden rounded-[40px] border border-black/10 bg-white/84 p-6 shadow-[0_24px_70px_rgba(16,20,23,0.08)] md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">后台策略</p>
              <h1 className="mt-3 text-3xl font-semibold md:text-4xl">模型路由与组合管理</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-black/62">
                这里决定大纲拆解、设定守护、逻辑挑刺、终稿收束这些后台职责分别调用哪一组模型。写手端不会看到这里的配置。
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-4 py-2 text-sm text-black/60">
                当前账号 {currentUser.email}
              </span>
              <Link
                className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/dashboard"
              >
                返回项目总览
              </Link>
              {selectedProjectId ? (
                <Link
                  className="rounded-full bg-ink px-4 py-3 text-sm font-semibold text-paper transition hover:bg-copper"
                  href={`/dashboard/projects/${selectedProjectId}/story-room`}
                >
                  查看当前项目
                </Link>
              ) : null}
            </div>
          </div>
        </section>

        {error ? (
          <section className="rounded-[28px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            {error}
          </section>
        ) : null}
        {success ? (
          <section className="rounded-[28px] border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-700">
            {success}
          </section>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="rounded-[34px] border border-black/10 bg-white/82 p-5 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-copper">项目</p>
                <h2 className="mt-2 text-2xl font-semibold">选择一本书</h2>
              </div>
              <button
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                onClick={() => void loadProjectList(queryInput)}
                type="button"
              >
                刷新
              </button>
            </div>

            <form className="mt-5 flex gap-2" onSubmit={(event) => void handleSearch(event)}>
              <input
                className="min-w-0 flex-1 rounded-full border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper"
                value={queryInput}
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder="搜索项目名 / 题材 / 邮箱"
              />
              <button
                className="rounded-full bg-ink px-4 py-3 text-sm font-semibold text-paper transition hover:bg-copper disabled:opacity-60"
                disabled={loadingList}
                type="submit"
              >
                搜索
              </button>
            </form>

            <div className="mt-5 space-y-3">
              {loadingList ? (
                Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-28 animate-pulse rounded-[24px] border border-black/8 bg-[#f8f3ea]"
                  />
                ))
              ) : projectSummaries.length > 0 ? (
                projectSummaries.map((summary) => {
                  const isActive = summary.project_id === selectedProjectId;
                  return (
                    <button
                      key={summary.project_id}
                      className={`w-full rounded-[24px] border px-4 py-4 text-left transition ${
                        isActive
                          ? "border-copper/25 bg-[#fbf3e8] shadow-[0_14px_28px_rgba(139,74,43,0.10)]"
                          : "border-black/10 bg-[#fbfaf5] hover:bg-white"
                      }`}
                      onClick={() => handleSelectProject(summary.project_id)}
                      type="button"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-black/82">
                            {summary.title}
                          </p>
                          <p className="mt-2 text-xs leading-6 text-black/55">
                            {formatProjectMeta(summary)}
                          </p>
                        </div>
                        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                          {STATUS_LABELS[summary.status] ?? summary.status}
                        </span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                          {summary.active_preset_label ?? summary.active_preset_key}
                        </span>
                        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/55">
                          微调 {summary.manual_override_count}
                        </span>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-black/48">
                        {summary.owner_email ? <span>{summary.owner_email}</span> : null}
                        <span>更新 {formatDateTime(summary.updated_at)}</span>
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-[24px] border border-dashed border-black/10 bg-[#fbfaf5] px-4 py-8 text-sm leading-7 text-black/52">
                  当前没有可管理项目，或者搜索结果为空。
                </div>
              )}
            </div>
          </aside>

          <section className="space-y-6">
            <section className="rounded-[34px] border border-black/10 bg-white/84 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)] md:p-7">
              {loadingDetail ? (
                <div className="space-y-4">
                  <div className="h-8 w-56 animate-pulse rounded-full bg-[#f3eadc]" />
                  <div className="grid gap-4 md:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div
                        key={index}
                        className="h-24 animate-pulse rounded-[24px] border border-black/8 bg-[#f8f3ea]"
                      />
                    ))}
                  </div>
                </div>
              ) : routingData && selectedProjectSummary ? (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-copper">当前项目</p>
                      <h2 className="mt-2 text-3xl font-semibold">{routingData.project.title}</h2>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          所有者 {selectedProjectSummary.owner_email ?? "未知"}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          组合 {presetMap[activePresetKey]?.label ?? activePresetKey}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          微调 {Object.keys(manualOverrides).length}
                        </span>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          最近更新 {formatDateTime(selectedProjectSummary.updated_at)}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <button
                        className="rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:opacity-50"
                        disabled={Object.keys(manualOverrides).length === 0}
                        onClick={handleClearOverrides}
                        type="button"
                      >
                        清空全部微调
                      </button>
                      <button
                        className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={!isDirty || saving}
                        onClick={() => void handleSave()}
                        type="button"
                      >
                        {saving ? "保存中..." : "保存后台策略"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
                    <article className="rounded-[26px] border border-black/10 bg-[#fbfaf5] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-copper">组合</p>
                      <h3 className="mt-2 text-xl font-semibold">先选一套默认组合</h3>
                      <select
                        className="mt-4 w-full rounded-[20px] border border-black/10 bg-white px-4 py-3 text-sm outline-none transition focus:border-copper"
                        onChange={(event) => handlePresetChange(event.target.value)}
                        value={activePresetKey}
                      >
                        {routingData.presets.map((preset) => (
                          <option key={preset.key} value={preset.key}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                      <p className="mt-4 text-sm leading-7 text-black/60">
                        {presetMap[activePresetKey]?.description ?? "当前组合没有补充说明。"}
                      </p>
                    </article>

                    <article className="rounded-[26px] border border-black/10 bg-[#fbfaf5] p-5">
                      <p className="text-xs uppercase tracking-[0.18em] text-copper">模型池</p>
                      <h3 className="mt-2 text-xl font-semibold">当前可用模型</h3>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {routingData.available_models.map((model) => (
                          <span
                            key={model.id}
                            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs text-black/60"
                          >
                            {model.label}
                          </span>
                        ))}
                      </div>
                      <p className="mt-4 text-sm leading-7 text-black/60">
                        改完后会直接覆盖该项目的后台策略，写手端依然只看到统一的一键式创作流程。
                      </p>
                    </article>
                  </div>
                </>
              ) : (
                <div className="rounded-[26px] border border-dashed border-black/10 bg-[#fbfaf5] px-5 py-10 text-sm leading-7 text-black/52">
                  先在左侧选一本书，再查看和修改它的后台模型组合。
                </div>
              )}
            </section>

            {routingData ? (
              <section className="grid gap-4 lg:grid-cols-2">
                {routingData.role_catalog.map((role) => {
                  const baseRoute = currentPresetRouting[role.role_key];
                  const effectiveRoute = effectiveRouting[role.role_key];
                  const overrideRoute = manualOverrides[role.role_key] ?? null;
                  const selectedModel = routingData.available_models.find(
                    (item) => item.id === effectiveRoute?.model,
                  );

                  return (
                    <article
                      key={role.role_key}
                      className="rounded-[30px] border border-black/10 bg-white/84 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-copper">
                            {role.role_key}
                          </p>
                          <h3 className="mt-2 text-2xl font-semibold">{role.label}</h3>
                          <p className="mt-3 text-sm leading-7 text-black/60">
                            {role.description}
                          </p>
                        </div>
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${
                            overrideRoute
                              ? "border-copper/20 bg-[#fbf3e8] text-copper"
                              : "border-black/10 bg-[#fbfaf5] text-black/55"
                          }`}
                        >
                          {overrideRoute ? "已微调" : "跟随组合"}
                        </span>
                      </div>

                      <div className="mt-5 grid gap-4">
                        <label className="block">
                          <span className="text-sm text-black/60">模型</span>
                          <select
                            className="mt-2 w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper"
                            onChange={(event) => {
                              const nextModel =
                                routingData.available_models.find(
                                  (item) => item.id === event.target.value,
                                ) ?? null;
                              handleRoleRouteChange(
                                role.role_key,
                                {
                                  model: event.target.value,
                                  reasoning_effort:
                                    nextModel?.supports_reasoning_effort === false
                                      ? null
                                      : effectiveRoute?.reasoning_effort ?? null,
                                },
                                nextModel ?? undefined,
                              );
                            }}
                            value={effectiveRoute?.model ?? ""}
                          >
                            {routingData.available_models.map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.label}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="block">
                          <span className="text-sm text-black/60">推理强度</span>
                          <select
                            className="mt-2 w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none transition focus:border-copper disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={selectedModel?.supports_reasoning_effort === false}
                            onChange={(event) =>
                              handleRoleRouteChange(role.role_key, {
                                reasoning_effort:
                                  event.target.value === ""
                                    ? null
                                    : (event.target.value as StoryEngineReasoningEffort),
                              })
                            }
                            value={effectiveRoute?.reasoning_effort ?? ""}
                          >
                            <option value="">不设置</option>
                            {routingData.available_reasoning_efforts.map((effort) => (
                              <option key={effort} value={effort}>
                                {effort}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="mt-5 rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
                        <p className="text-xs uppercase tracking-[0.16em] text-copper">
                          当前生效
                        </p>
                        <p className="mt-2 text-sm font-semibold text-black/82">
                          {effectiveRoute
                            ? `${modelNameById(routingData.available_models, effectiveRoute.model)} / ${
                                effectiveRoute.reasoning_effort ?? "不设置"
                              }`
                            : "暂无配置"}
                        </p>
                        <p className="mt-3 text-xs leading-6 text-black/55">
                          组合默认：
                          {baseRoute
                            ? ` ${modelNameById(routingData.available_models, baseRoute.model)} / ${
                                baseRoute.reasoning_effort ?? "不设置"
                              }`
                            : " 暂无"}
                        </p>
                        {selectedModel?.description ? (
                          <p className="mt-3 text-xs leading-6 text-black/55">
                            {selectedModel.description}
                          </p>
                        ) : null}
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        {(selectedModel?.recommended_roles ?? []).includes(role.role_key) ? (
                          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                            推荐用于当前职责
                          </span>
                        ) : null}
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                          提供方 {selectedModel?.provider ?? "未知"}
                        </span>
                        {overrideRoute ? (
                          <button
                            className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                            onClick={() => handleResetRole(role.role_key)}
                            type="button"
                          >
                            恢复默认
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </section>
            ) : null}
          </section>
        </section>
      </div>
    </main>
  );
}

function ModelRoutingAdminPageFallback() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#fbf6ee,transparent_38%),linear-gradient(180deg,#f7f0e3_0%,#f2ebde_100%)] px-4 py-8 md:px-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="h-44 animate-pulse rounded-[40px] border border-black/8 bg-white/70" />
        <section className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <div className="h-[620px] animate-pulse rounded-[34px] border border-black/8 bg-white/70" />
          <div className="space-y-6">
            <div className="h-64 animate-pulse rounded-[34px] border border-black/8 bg-white/70" />
            <div className="grid gap-4 lg:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="h-72 animate-pulse rounded-[30px] border border-black/8 bg-white/70"
                />
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function ModelRoutingAdminPage() {
  return (
    <Suspense fallback={<ModelRoutingAdminPageFallback />}>
      <ModelRoutingAdminPageBody />
    </Suspense>
  );
}
