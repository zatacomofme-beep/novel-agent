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

export function StoryRoomSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="rounded-[42px] border border-black/10 bg-white/78 p-8 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <SkeletonLine className="h-4 w-24" />
        <div className="mt-4 space-y-3">
          <SkeletonLine className="h-8 w-64" />
          <SkeletonLine className="h-4 w-32" />
        </div>

        <div className="mt-8 flex gap-3">
          <div className="h-10 w-32 rounded-full bg-black/5" />
          <div className="h-10 w-32 rounded-full bg-black/5" />
          <div className="h-10 w-32 rounded-full bg-black/5" />
        </div>

        <div className="mt-6 rounded-[28px] border border-copper/20 bg-[#fff7ef] p-5">
          <SkeletonLine className="h-4 w-24" />
          <SkeletonLine className="mt-3 h-6 w-48" />
          <SkeletonLine className="mt-3 h-4 w-full" />
          <SkeletonLine className="mt-2 h-4 w-3/4" />
          <div className="mt-4 flex gap-3">
            <div className="h-11 w-36 rounded-full bg-black/5" />
            <div className="h-11 w-28 rounded-full bg-black/5" />
          </div>
        </div>
      </div>

      <div className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
        <SkeletonLine className="h-5 w-32" />
        <SkeletonLine className="mt-3 h-8 w-48" />
        <div className="mt-4 flex flex-wrap gap-2">
          <div className="h-6 w-20 rounded-full bg-black/5" />
          <div className="h-6 w-24 rounded-full bg-black/5" />
          <div className="h-6 w-16 rounded-full bg-black/5" />
        </div>
        <div className="mt-4 flex gap-3">
          <div className="h-11 w-28 rounded-full bg-black/5" />
          <div className="h-11 w-36 rounded-full bg-black/5" />
        </div>
      </div>
    </div>
  );
}
