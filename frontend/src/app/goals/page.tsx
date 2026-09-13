"use client";

import { useEffect, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { fetchGoals, getTelegramId, type Goal } from "@/lib/api";

const DISTANCE_LABELS: Record<string, string> = {
  "5k": "5 км",
  "10k": "10 км",
  half: "Полумарафон",
  marathon: "Марафон",
};

function formatTime(seconds: number | null) {
  if (!seconds) return "Финиш";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadGoals = async () => {
    if (!getTelegramId() || !localStorage.getItem("access_token")) {
      window.location.href = "/";
      return;
    }
    try {
      setLoading(true);
      setError("");
      setGoals(await fetchGoals());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить цели");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGoals();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Мои цели</h1>
      {loading ? (
        <LoadingSpinner label="Загружаем цели" />
      ) : error ? (
        <ErrorState message={error} onRetry={loadGoals} />
      ) : goals.length === 0 ? (
        <p className="text-gray-500">Нет целей. Создайте цель через Telegram-бот.</p>
      ) : (
        <div className="space-y-4">
          {goals.map((g) => (
            <div key={g.id} className="bg-white p-5 rounded-xl border shadow-sm">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-lg">{DISTANCE_LABELS[g.distance] || g.distance}</h3>
                  <p className="text-gray-500">Дата: {g.race_date}</p>
                  <p className="text-gray-500">Цель: {formatTime(g.target_time_seconds)}</p>
                </div>
                <span className="bg-blue-100 text-blue-800 text-sm px-3 py-1 rounded-full">
                  {g.days_until_race} дн.
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
