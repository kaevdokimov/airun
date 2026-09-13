"use client";

import { useEffect, useState } from "react";
import { AUTH_EXPIRED_EVENT } from "@/lib/api";

export function AuthNotice() {
  const [message, setMessage] = useState("");

  useEffect(() => {
    function handleAuthExpired(event: Event) {
      const detail = event instanceof CustomEvent ? event.detail : "";
      setMessage(detail || "Сессия истекла. Сейчас вернём вас на вход.");
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  }, []);

  if (!message) return null;

  return (
    <div className="fixed right-4 top-4 z-50 max-w-sm rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm">
      {message}
    </div>
  );
}
