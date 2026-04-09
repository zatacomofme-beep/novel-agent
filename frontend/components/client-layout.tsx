"use client";

import { ToastProvider } from "@/components/toast-provider";
import { GlobalNavbar } from "@/components/global-navbar";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <GlobalNavbar />
      {children}
    </ToastProvider>
  );
}
