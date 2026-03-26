"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { formatDateTime } from "@/app/dashboard/_components/quality-trend";
import {
  StyleControlPanel,
  type StylePreferencePayload,
} from "@/components/story-engine/style-control-panel";
import { apiFetchWithAuth } from "@/lib/api";
import { loadAuthSession } from "@/lib/auth";
import type { StyleTemplate, User, UserPreferenceProfile } from "@/types/api";

const STYLE_CENTER_SAMPLE_STORAGE_KEY = "novel-agent:style-center-sample";

function StyleCenterShell() {
  const searchParams = useSearchParams();
  const returnProjectId = searchParams.get("projectId");
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [preferenceProfile, setPreferenceProfile] = useState<UserPreferenceProfile | null>(null);
  const [styleTemplates, setStyleTemplates] = useState<StyleTemplate[]>([]);
  const [styleSample, setStyleSample] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const session = loadAuthSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setCurrentUser(session.user);
    void loadStyleCenterState();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const savedSample = window.localStorage.getItem(STYLE_CENTER_SAMPLE_STORAGE_KEY);
    if (savedSample) {
      setStyleSample(savedSample);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(STYLE_CENTER_SAMPLE_STORAGE_KEY, styleSample);
  }, [styleSample]);

  async function loadStyleCenterState(showSpinner = true) {
    if (showSpinner) {
      setLoading(true);
    }
    setError(null);
    try {
      const [profileData, templateData] = await Promise.all([
        apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences"),
        apiFetchWithAuth<StyleTemplate[]>("/api/v1/profile/style-templates"),
      ]);
      setPreferenceProfile(profileData);
      setStyleTemplates(templateData);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "加载风格中心失败。",
      );
      setPreferenceProfile(null);
      setStyleTemplates([]);
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  }

  async function handleApplyStyleTemplate(templateKey: string) {
    if (actionKey) {
      return;
    }
    setActionKey(`style:apply:${templateKey}`);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<UserPreferenceProfile>(
        `/api/v1/profile/style-templates/${templateKey}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ mode: "replace" }),
        },
      );
      await loadStyleCenterState(false);
      setSuccess("这套声音底稿已经套进你的长期偏好。");
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "套用声音底稿失败。",
      );
    } finally {
      setActionKey(null);
    }
  }

  async function handleClearStyleTemplate() {
    if (actionKey) {
      return;
    }
    setActionKey("style:clear");
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/style-templates/active", {
        method: "DELETE",
      });
      await loadStyleCenterState(false);
      setSuccess("当前声音底稿已经清掉。");
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "清除声音底稿失败。",
      );
    } finally {
      setActionKey(null);
    }
  }

  async function handleSavePreference(payload: StylePreferencePayload) {
    if (actionKey) {
      return;
    }
    setActionKey("style:save");
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadStyleCenterState(false);
      setSuccess("长期写法已经保存，后续起稿会优先按这套手感收束。");
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "保存长期写法失败。",
      );
    } finally {
      setActionKey(null);
    }
  }

  const stableSignals = useMemo(
    () => preferenceProfile?.learning_snapshot.stable_preferences.slice(0, 4) ?? [],
    [preferenceProfile],
  );

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="text-sm uppercase tracking-[0.24em] text-copper">风格中心</p>
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
        <section className="rounded-[36px] border border-black/10 bg-white/78 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-copper">风格中心</p>
              <h1 className="mt-3 text-4xl font-semibold">先把整本书的声音定稳</h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-black/62">
                这里专门整理你的长期写法、常用底稿和稳定偏好。正文区只保留本章临时参考，整本书的手感在这里收口。
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium transition hover:bg-[#f6f0e6]"
                href="/dashboard"
              >
                回书架
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

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm text-black/55">当前底稿</p>
              <p className="mt-3 text-2xl font-semibold">
                {preferenceProfile?.active_template?.name ?? "未套底稿"}
              </p>
            </article>
            <article className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm text-black/55">完成度</p>
              <p className="mt-3 text-2xl font-semibold">
                {preferenceProfile ? `${(preferenceProfile.completion_score * 100).toFixed(0)}%` : "-"}
              </p>
            </article>
            <article className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm text-black/55">学习次数</p>
              <p className="mt-3 text-2xl font-semibold">
                {preferenceProfile?.learning_snapshot.observation_count ?? 0}
              </p>
            </article>
            <article className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm text-black/55">最近更新</p>
              <p className="mt-3 text-2xl font-semibold">
                {preferenceProfile ? formatDateTime(preferenceProfile.updated_at) : "-"}
              </p>
            </article>
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

        <section className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
          <StyleControlPanel
            mode="center"
            chapterSample={styleSample}
            preferenceProfile={preferenceProfile}
            styleTemplates={styleTemplates}
            loading={loading}
            actionKey={actionKey}
            onChapterSampleChange={setStyleSample}
            onApplyTemplate={handleApplyStyleTemplate}
            onClearTemplate={handleClearStyleTemplate}
            onSavePreference={handleSavePreference}
          />

          <div className="grid gap-6">
            <section className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.2em] text-copper">稳定偏向</p>
              {stableSignals.length > 0 ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {stableSignals.map((signal) => (
                    <span
                      key={`${signal.field}-${signal.value}`}
                      className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/65"
                    >
                      {signal.field} · {signal.value}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-black/60">当前还没有足够稳定的长期偏向。</p>
              )}

              {preferenceProfile?.learning_snapshot.summary ? (
                <div className="mt-4 rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/68">
                  {preferenceProfile.learning_snapshot.summary}
                </div>
              ) : null}
            </section>

            <section className="rounded-[32px] border border-black/10 bg-white/80 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <p className="text-xs uppercase tracking-[0.2em] text-copper">什么时候来这里</p>
              <div className="mt-4 grid gap-3 text-sm text-black/68">
                <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3">
                  开新书前，先选一套声音底稿。
                </div>
                <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3">
                  觉得最近几章越写越不像自己时，回来重新压一遍长期手感。
                </div>
                <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3">
                  想切换题材时，先在这里换底稿，再回去继续写正文。
                </div>
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function PreferencesPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen px-6 py-10">
          <div className="mx-auto max-w-7xl rounded-[36px] border border-black/10 bg-white/75 p-10 text-sm text-black/55">
            正在装载风格中心...
          </div>
        </main>
      }
    >
      <StyleCenterShell />
    </Suspense>
  );
}
