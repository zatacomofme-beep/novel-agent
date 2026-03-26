"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState, Suspense } from "react";

import { apiFetch } from "@/lib/api";
import { saveAuthSession } from "@/lib/auth";
import type { TokenResponse } from "@/types/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect");
  const registerHref =
    redirect && redirect.startsWith("/")
      ? `/register?redirect=${encodeURIComponent(redirect)}`
      : "/register";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const session = await apiFetch<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      saveAuthSession(session);
      router.push(redirect && redirect.startsWith("/") ? redirect : "/dashboard");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Login failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative overflow-hidden rounded-[40px] border border-black/10 bg-white/76 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)] backdrop-blur md:p-10">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[rgba(139,74,43,0.08)] blur-3xl" />
        <div className="absolute bottom-0 left-0 h-36 w-36 rounded-full bg-[rgba(86,98,70,0.08)] blur-3xl" />

        <p className="relative text-sm uppercase tracking-[0.24em] text-copper">账号登录</p>
        <h1 className="relative mt-4 text-4xl font-semibold leading-tight md:text-5xl">
          回到你的写作台，
          <br />
          继续往下写。
        </h1>
        <p className="relative mt-6 max-w-2xl text-base leading-8 text-black/68">
          登录后会直接进入书架。你可以继续当前项目，或者马上开始新的一本书。
        </p>

        <div className="relative mt-8 flex flex-wrap gap-2">
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            继续写正文
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            看优化稿
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
            自动记设定
          </span>
        </div>
      </section>

      <section className="rounded-[36px] border border-black/10 bg-white/82 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)] backdrop-blur">
        <p className="text-sm uppercase tracking-[0.22em] text-copper">登录</p>
        <h2 className="mt-3 text-3xl font-semibold">进入工作台</h2>

        <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit}>
          <label className="flex flex-col gap-2 text-sm">
            邮箱
            <input
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label className="flex flex-col gap-2 text-sm">
            密码
            <input
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
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
            className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={loading}
          >
            {loading ? "登录中..." : "登录"}
          </button>
        </form>

        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-black/65">
          <span>还没有账号？</span>
          <Link className="text-copper underline-offset-4 hover:underline" href={registerHref}>
            去注册
          </Link>
        </div>
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10 md:px-8">
      <Suspense
        fallback={
          <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="min-h-[320px] rounded-[40px] border border-black/10 bg-white/75 p-8 animate-pulse" />
            <div className="min-h-[320px] rounded-[36px] border border-black/10 bg-white/75 p-8 animate-pulse" />
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}
