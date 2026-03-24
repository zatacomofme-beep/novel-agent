"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState, Suspense } from "react";

import { apiFetch } from "@/lib/api";
import { saveAuthSession } from "@/lib/auth";
import type { TokenResponse } from "@/types/api";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect");
  const loginHref =
    redirect && redirect.startsWith("/")
      ? `/login?redirect=${encodeURIComponent(redirect)}`
      : "/login";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const session = await apiFetch<TokenResponse>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      saveAuthSession(session);
      router.push(redirect && redirect.startsWith("/") ? redirect : "/dashboard");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Register failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
      <p className="text-sm uppercase tracking-[0.24em] text-moss">创建账号</p>
      <h1 className="mt-3 text-3xl font-semibold">创建账号</h1>
      <p className="mt-3 text-sm leading-7 text-black/65">
        注册完成后会直接进入项目页，你可以马上开始定大纲、写正文和沉淀设定。
      </p>

      <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit}>
        <label className="flex flex-col gap-2 text-sm">
          邮箱
          <input
            className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-moss"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="flex flex-col gap-2 text-sm">
          密码
          <input
            className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-moss"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            required
          />
        </label>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          className="rounded-2xl bg-moss px-4 py-3 text-sm font-medium text-paper transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={loading}
        >
          {loading ? "创建中..." : "注册"}
        </button>
      </form>

      <p className="mt-6 text-sm text-black/65">
        已有账号？
        <Link className="ml-2 text-moss underline-offset-4 hover:underline" href={loginHref}>
          去登录
        </Link>
      </p>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <Suspense fallback={<div className="w-full max-w-md rounded-3xl border border-black/10 bg-white/75 p-8 animate-pulse" />}>
        <RegisterForm />
      </Suspense>
    </main>
  );
}
