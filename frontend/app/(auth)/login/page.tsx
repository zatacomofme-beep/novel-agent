"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiFetch } from "@/lib/api";
import { saveAuthSession } from "@/lib/auth";
import type { TokenResponse } from "@/types/api";

export default function LoginPage() {
  const router = useRouter();
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
      router.push("/dashboard");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Login failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-md rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
        <p className="text-sm uppercase tracking-[0.24em] text-copper">Auth</p>
        <h1 className="mt-3 text-3xl font-semibold">登录工作台</h1>
        <p className="mt-3 text-sm leading-7 text-black/65">
          当前使用后端 JWT 接口建立基础登录态，后续会接入完整鉴权流与路由保护。
        </p>

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

        <p className="mt-6 text-sm text-black/65">
          还没有账号？
          <Link className="ml-2 text-copper underline-offset-4 hover:underline" href="/register">
            去注册
          </Link>
        </p>
      </div>
    </main>
  );
}
