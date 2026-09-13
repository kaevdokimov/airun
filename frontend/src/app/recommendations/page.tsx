"use client";

import { useEffect, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { fetchRecommendations, getTelegramId, type Recommendation } from "@/lib/api";

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadRecommendations = async () => {
    if (!getTelegramId() || !localStorage.getItem("access_token")) {
      window.location.href = "/";
      return;
    }
    try {
      setLoading(true);
      setError("");
      setRecs(await fetchRecommendations());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить рекомендации");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecommendations();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">AI-рекомендации</h1>
      {loading ? (
        <LoadingSpinner label="Загружаем рекомендации" />
      ) : error ? (
        <ErrorState message={error} onRetry={loadRecommendations} />
      ) : recs.length === 0 ? (
        <p className="text-gray-500">Пока нет рекомендаций. Создайте цель и подключите Garmin.</p>
      ) : (
        <div className="space-y-6">
          {recs.map((rec) => (
            <div key={rec.id} className="bg-white p-6 rounded-xl border shadow-sm">
              <p className="text-sm text-gray-400 mb-3">
                {new Date(rec.generated_at).toLocaleString("ru-RU")}
              </p>
              {rec.parsed ? (
                <div className="space-y-3">
                  <p className="font-medium">{rec.parsed.summary}</p>
                  <p>
                    <span className="font-medium">Сегодня: </span>
                    {rec.parsed.today_recommendation}
                  </p>
                  {rec.parsed.progress_to_goal && (
                    <p className="text-brand">{rec.parsed.progress_to_goal}</p>
                  )}
                  {rec.parsed.week_plan?.length > 0 && (
                    <ul className="list-disc list-inside text-sm text-gray-600">
                      {rec.parsed.week_plan.map((d, i) => (
                        <li key={i}>{d}</li>
                      ))}
                    </ul>
                  )}
                  {rec.parsed.warnings?.length > 0 && (
                    <div className="bg-yellow-50 p-3 rounded-lg text-sm">
                      {rec.parsed.warnings.map((w, i) => (
                        <p key={i}>⚠️ {w}</p>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{rec.content}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
