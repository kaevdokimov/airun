"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchWeekStats, getTelegramId, type WeekStats } from "@/lib/api";

export default function StatsPage() {
  const [stats, setStats] = useState<WeekStats | null>(null);

  useEffect(() => {
    if (!getTelegramId() || !localStorage.getItem("access_token")) {
      window.location.href = "/";
      return;
    }
    fetchWeekStats().then(setStats);
  }, []);

  if (!stats) {
    return <p className="text-gray-500">Загрузка...</p>;
  }

  const chartData = stats.activities
    .filter((a) => a.distance_m)
    .map((a) => ({
      date: new Date(a.started_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }),
      km: Math.round((a.distance_m || 0) / 100) / 10,
    }))
    .reverse();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Статистика за неделю</h1>
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-5 rounded-xl border">
          <p className="text-gray-500 text-sm">Пробежек</p>
          <p className="text-3xl font-bold">{stats.activity_count}</p>
        </div>
        <div className="bg-white p-5 rounded-xl border">
          <p className="text-gray-500 text-sm">Дистанция</p>
          <p className="text-3xl font-bold">{(stats.total_distance_m / 1000).toFixed(1)} км</p>
        </div>
        <div className="bg-white p-5 rounded-xl border">
          <p className="text-gray-500 text-sm">Время</p>
          <p className="text-3xl font-bold">{Math.round(stats.total_duration_sec / 60)} мин</p>
        </div>
      </div>
      {chartData.length > 0 && (
        <div className="bg-white p-6 rounded-xl border">
          <h2 className="font-semibold mb-4">Дистанция по пробежкам</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis unit=" км" />
              <Tooltip />
              <Bar dataKey="km" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
