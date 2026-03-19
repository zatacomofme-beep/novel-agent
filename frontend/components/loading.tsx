"use client";

export function PageLoader() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 animate-ping rounded-full bg-copper/20"></div>
          <div className="absolute inset-0 animate-pulse rounded-full bg-copper/40"></div>
          <div className="absolute inset-3 animate-spin rounded-full border-2 border-copper border-t-transparent"></div>
        </div>
        <p className="text-sm text-black/50">加载中...</p>
      </div>
    </div>
  );
}

export function SectionLoader() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-copper border-t-transparent"></div>
    </div>
  );
}

export function ButtonLoader({ label = "处理中" }: { label?: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
      {label}
    </span>
  );
}
