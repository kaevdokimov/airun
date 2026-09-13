import type { Metadata } from "next";
import { AuthNotice } from "@/components/AuthNotice";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIRun — AI Running Coach",
  description: "Garmin fitness data + AI coaching",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <nav className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-brand">
              AIRun
            </a>
            <div className="flex gap-4 text-sm">
              <a href="/goals" className="hover:text-brand">Цели</a>
              <a href="/stats" className="hover:text-brand">Статистика</a>
              <a href="/recommendations" className="hover:text-brand">Рекомендации</a>
            </div>
          </div>
        </nav>
        <AuthNotice />
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
