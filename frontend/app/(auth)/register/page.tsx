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
    <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.02fr_0.98fr]">
      <section className="relative overflow-hidden rounded-[40px] border border-black/10 bg-white/76 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)] backdrop-blur md:p-10">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[rgba(86,98,70,0.08)] blur-3xl" />
        <div className="absolute bottom-0 left-0 h-36 w-36 rounded-full bg-[rgba(139,74,43,0.08)] blur-3xl" />

        <p className="relative text-sm uppercase tracking-[0.24em] text-moss">创建账号</p>
        <h1 className="relative mt-4 text-4xl font-semibold leading-tight md:text-5xl">
          从第一本书开始，
          <br />
          把流程写顺。
        </h1>
        <p className="relative mt-6 max-w-2xl text-base leading-8 text-black/68">
          注册后会直接进入书架。接下来就是填书名、生成三级大纲、开始写正文。
        </p>

        <div className="relative mt-8 grid gap-3 sm:grid-cols-3">
          <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">01</p>
            <p className="mt-2 text-sm font-semibold">创建新书</p>
          </div>
          <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">02</p>
            <p className="mt-2 text-sm font-semibold">生成三级大纲</p>
          </div>
          <div className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">03</p>
            <p className="mt-2 text-sm font-semibold">开始写第一章</p>
          </div>
        </div>
      </section>

      <section className="rounded-[36px] border border-black/10 bg-white/82 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.08)] backdrop-blur">
        <p className="text-sm uppercase tracking-[0.22em] text-moss">注册</p>
        <h2 className="mt-3 text-3xl font-semibold">创建账号</h2>

        <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit}>
          <label className="flex flex-col gap-2 text-sm">
            邮箱
            <input
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-moss"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              data-testid="register-email-input"
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
              data-testid="register-password-input"
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
            data-testid="register-submit"
          >
            {loading ? "创建中..." : "注册"}
          </button>
        </form>

        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-black/65">
          <span>已有账号？</span>
          <Link className="text-moss underline-offset-4 hover:underline" href={loginHref}>
            去登录
          </Link>
        </div>
      </section>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <main
      className="flex min-h-screen items-center justify-center px-6 py-10 md:px-8"
      data-testid="register-page"
    >
      <Suspense
        fallback={
          <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.02fr_0.98fr]">
            <div className="min-h-[320px] rounded-[40px] border border-black/10 bg-white/75 p-8 animate-pulse" />
            <div className="min-h-[320px] rounded-[36px] border border-black/10 bg-white/75 p-8 animate-pulse" />
          </div>
        }
      >
        <RegisterForm />
      </Suspense>
    </main>
  );
}
