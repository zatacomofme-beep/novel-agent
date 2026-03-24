import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "网文创作平台",
  description: "面向长篇网文创作的一体化写作工作台。",
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
