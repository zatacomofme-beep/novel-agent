"use client";

import { ToastProvider } from "@/components/toast-provider";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}