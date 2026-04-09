"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function GlobalNavbar() {
  const pathname = usePathname();
  const isDashboard = pathname === "/dashboard";
  const isStoryRoom = pathname.includes("/story-room");

  return (
    <header className="sticky top-0 z-50 border-b border-black/8 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 text-sm font-semibold text-black/80 transition hover:text-copper"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
          <span>网文创作平台</span>
        </Link>

        <nav className="flex items-center gap-3">
          {isStoryRoom && (
            <Link
              href="/dashboard"
              className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs font-medium text-black/60 transition hover:bg-[#f6f0e6] hover:text-black/80"
            >
              项目总览
            </Link>
          )}
          {!isDashboard && !isStoryRoom && (
            <Link
              href="/dashboard"
              className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs font-medium text-black/60 transition hover:bg-[#f6f0e6] hover:text-black/80"
            >
              返回首页
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
