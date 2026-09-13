"use client";

import { useEffect, useRef, useState } from "react";
import { clearAuth, getTelegramId, loginWithTelegram } from "@/lib/api";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, string | number>) => void;
  }
}

export default function HomePage() {
  const [telegramId, setId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const widgetRef = useRef<HTMLDivElement>(null);
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "";

  useEffect(() => {
    setId(getTelegramId());
  }, []);

  useEffect(() => {
    if (telegramId || !botUsername || !widgetRef.current) return;

    window.onTelegramAuth = async (user) => {
      try {
        setError("");
        const data = await loginWithTelegram(user);
        setId(data.telegram_id);
      } catch {
        setError("Не удалось войти через Telegram");
      }
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    widgetRef.current.innerHTML = "";
    widgetRef.current.appendChild(script);

    return () => {
      delete window.onTelegramAuth;
    };
  }, [telegramId, botUsername]);

  if (!telegramId) {
    return (
      <div className="max-w-md mx-auto mt-16">
        <h1 className="text-3xl font-bold mb-4">AIRun Dashboard</h1>
        <p className="text-gray-600 mb-6">
          Войдите через Telegram для доступа к вашим данным.
        </p>
        {botUsername ? (
          <div ref={widgetRef} className="flex justify-center" />
        ) : (
          <p className="text-red-600 text-sm">
            Укажите NEXT_PUBLIC_TELEGRAM_BOT_USERNAME в .env
          </p>
        )}
        {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Добро пожаловать в AIRun</h1>
          <p className="text-gray-600">
            Ваш AI-тренер для бега. Основной интерфейс — Telegram-бот.
          </p>
        </div>
        <button
          onClick={() => {
            clearAuth();
            setId(null);
          }}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Выйти
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <a href="/goals" className="bg-white p-6 rounded-xl shadow-sm border hover:border-brand transition">
          <h2 className="text-lg font-semibold mb-2">🎯 Цели</h2>
          <p className="text-gray-500 text-sm">Управление беговыми целями</p>
        </a>
        <a href="/stats" className="bg-white p-6 rounded-xl shadow-sm border hover:border-brand transition">
          <h2 className="text-lg font-semibold mb-2">📊 Статистика</h2>
          <p className="text-gray-500 text-sm">Данные из Garmin Connect</p>
        </a>
        <a href="/recommendations" className="bg-white p-6 rounded-xl shadow-sm border hover:border-brand transition">
          <h2 className="text-lg font-semibold mb-2">💡 Рекомендации</h2>
          <p className="text-gray-500 text-sm">AI-советы от тренера</p>
        </a>
      </div>
    </div>
  );
}
