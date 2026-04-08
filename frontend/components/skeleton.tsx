"use client";

import { cn } from "@/lib/utils";

function SkeletonLine({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-4 rounded bg-black/5 animate-pulse",
        className,
      )}
    />
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <SkeletonLine className="h-8 w-48" />
        <SkeletonLine className="h-10 w-32" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border border-black/8 p-5 space-y-3">
            <SkeletonLine className="h-4 w-24" />
            <SkeletonLine className="h-7 w-16" />
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-black/8 p-5 space-y-4">
        <SkeletonLine className="h-5 w-32" />
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <SkeletonLine className="h-10 w-10 flex-shrink-0 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <SkeletonLine className="h-4 w-3/4" />
                <SkeletonLine className="h-3 w-1/2" />
              </div>
              <SkeletonLine className="h-6 w-16 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-black/8 p-5 space-y-3">
          <SkeletonLine className="h-5 w-28" />
          <div className="h-48 rounded-lg bg-black/4" />
        </div>
        <div className="rounded-xl border border-black/8 p-5 space-y-3">
          <SkeletonLine className="h-5 w-28" />
          <div className="h-48 rounded-lg bg-black/4" />
        </div>
      </div>
    </div>
  );
}

export function StoryRoomSkeleton() {
  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <aside className="hidden w-56 shrink-0 border-r border-black/8 p-4 lg:block space-y-3">
        <SkeletonLine className="h-5 w-24" />
        {[...Array(8)].map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <SkeletonLine className="h-4 w-6" />
            <SkeletonLine className={cn("h-4", i === 0 ? "w-32" : "w-24")} />
          </div>
        ))}
      </aside>

      <main className="flex-1 overflow-auto p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <SkeletonLine className="h-6 w-48" />
            <SkeletonLine className="h-4 w-32" />
          </div>
          <div className="flex gap-2">
            <SkeletonLine className="h-9 w-20" />
            <SkeletonLine className="h-9 w-20" />
          </div>
        </div>

        <div className="rounded-xl border border-black/8 p-5 space-y-3">
          <div className="flex gap-2">
            {[...Array(4)].map((_, i) => (
              <SkeletonLine key={i} className={cn("h-8", i === 0 ? "w-24" : "w-16")} />
            ))}
          </div>
          <div className="space-y-2 pt-2">
            {[...Array(12)].map((_, i) => (
              <SkeletonLine
                key={i}
                className={cn(
                  i === 3 || i === 7 ? "w-2/3" : "w-full",
                )}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-xl border border-black/8 overflow-hidden">
      <div className="border-b border-black/8 bg-black/[0.02] px-4 py-3">
        <div className="flex gap-4">
          {[...Array(cols)].map((_, i) => (
            <SkeletonLine key={i} className={cn("h-4", i === 0 ? "w-24" : "flex-1")} />
          ))}
        </div>
      </div>
      <div className="divide-y divide-black/[0.04]">
        {[...Array(rows)].map((_, rowIdx) => (
          <div key={rowIdx} className="px-4 py-3">
            <div className="flex gap-4">
              {[...Array(cols)].map((_, colIdx) => (
                <SkeletonLine
                  key={colIdx}
                  className={cn(
                    "h-4",
                    colIdx === 0 ? "w-20" : colIdx === 1 ? "w-32" : "flex-1",
                  )}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function InlineSpinner({ size = "md", label = "加载中..." }: { size?: "sm" | "md" | "lg"; label?: string }) {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-6 w-6",
    lg: "h-8 w-8",
  };

  return (
    <div className="flex items-center gap-2 text-black/40">
      <svg
        className={cn("animate-spin text-current", sizeClasses[size])}
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <span className="text-sm">{label}</span>
    </div>
  );
}
