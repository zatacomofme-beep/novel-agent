"use client";

import { useEffect, useState } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <html lang="zh-CN">
      <body>
        <div className="flex min-h-screen items-center justify-center px-6">
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
            <h1 className="mt-6 text-xl font-semibold text-red-800">
              抱歉，发生了意外错误
            </h1>
            <p className="mt-2 text-sm text-red-600">{error.message}</p>
            {error.digest && (
              <p className="mt-1 text-xs text-red-400">错误码: {error.digest}</p>
            )}
            <div className="mt-6 flex flex-col gap-3">
              <button
                onClick={reset}
                className="rounded-2xl bg-red-600 px-6 py-3 text-sm font-medium text-white hover:bg-red-700"
              >
                重试
              </button>
              <button
                onClick={() => (window.location.href = "/")}
                className="rounded-2xl border border-red-300 bg-white px-6 py-3 text-sm font-medium text-red-700 hover:bg-red-100"
              >
                返回首页
              </button>
            </div>
            {showDetails && error.stack && (
              <pre className="mt-6 text-left overflow-auto rounded-lg bg-red-100 p-4 text-xs text-red-700">
                {error.stack}
              </pre>
            )}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="mt-4 text-xs text-red-500 hover:text-red-700"
            >
              {showDetails ? "收起详情" : "显示详情"}
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
