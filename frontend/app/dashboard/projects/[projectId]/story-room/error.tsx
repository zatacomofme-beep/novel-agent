"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api";
import { classifyError, type AppErrorCategory } from "@/lib/errors";

const CATEGORY_TITLES: Record<AppErrorCategory, string> = {
  network: "网络连接失败",
  auth: "登录已过期",
  permission: "没有访问权限",
  not_found: "资源不存在",
  conflict: "操作冲突",
  validation: "输入有误",
  server: "服务暂时不可用",
  unknown: "抱歉，发生了意外错误",
};

export default function StoryRoomError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const params = useParams<{ projectId?: string }>();
  const classified = classifyError(error);
  const traceId = error instanceof ApiError ? error.traceId : "";

  useEffect(() => {
    console.error("[StoryRoom Error]", {
      message: error.message,
      category: classified.category,
      digest: error.digest ?? null,
      projectId: params.projectId ?? null,
      stack: error.stack ?? null,
    });
  }, [error, classified.category, params.projectId]);

  const handleReLogin = () => {
    window.location.href = "/api/v1/auth/login";
  };

  const title = CATEGORY_TITLES[classified.category] ?? CATEGORY_TITLES.unknown;

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-6">
      <div className="w-full max-w-lg rounded-3xl border border-red-200 bg-red-50 p-8 text-center shadow-xl">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
          <svg
            className="h-8 w-8 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h1 className="mt-6 text-xl font-semibold text-red-800">{title}</h1>
        <p className="mt-2 text-sm text-red-600">{classified.userMessage}</p>
        {error.message && classified.category !== "network" && (
          <p className="mt-2 rounded-xl bg-red-100/60 p-3 text-left font-mono text-xs text-red-500 break-all">
            {error.message}
          </p>
        )}
        {error.digest && (
          <p className="mt-1 text-xs text-red-400">错误码: {error.digest}</p>
        )}
        {traceId && (
          <p className="mt-1 text-xs text-red-400">
            追踪ID: <span className="font-mono select-all">{traceId}</span>
          </p>
        )}
        <div className="mt-6 flex flex-col gap-3">
          {classified.category === "auth" ? (
            <button
              onClick={handleReLogin}
              className="rounded-2xl bg-red-600 px-6 py-3 text-sm font-medium text-white hover:bg-red-700"
            >
              重新登录
            </button>
          ) : (
            <button
              onClick={reset}
              className="rounded-2xl bg-red-600 px-6 py-3 text-sm font-medium text-white hover:bg-red-700"
            >
              重试
            </button>
          )}
          <button
            onClick={() => (window.location.href = "/dashboard")}
            className="rounded-2xl border border-red-300 bg-white px-6 py-3 text-sm font-medium text-red-700 hover:bg-red-100"
          >
            返回项目总览
          </button>
        </div>
      </div>
    </div>
  );
}
