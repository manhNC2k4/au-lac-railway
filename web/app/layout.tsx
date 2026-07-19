import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/providers/query-provider";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: {
    default: "Âu Lạc Railway — Điều hành doanh thu",
    template: "%s · Âu Lạc Railway",
  },
  icons: {
    icon: [
      {
        url: "/images/aulac-train-favicon-v2.png?v=3",
        type: "image/png",
        sizes: "any",
      },
    ],
    shortcut: "/images/aulac-train-favicon-v2.png?v=3",
    apple: "/images/aulac-train-favicon-v2.png?v=3",
  },
  description:
    "Công cụ nội bộ demo quản trị doanh thu đường sắt: cắt chặng, ghép chặng, giá vé linh hoạt.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
