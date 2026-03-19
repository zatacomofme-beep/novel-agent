import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Long Novel Agent",
  description: "A deep AI collaboration system for long-form fiction writing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
