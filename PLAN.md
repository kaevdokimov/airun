# План исправлений AIRun

> Приоритет: P0 (блокирует/ломает) → P1 (надёжность) → P2 (архитектура) → P3 (UX/polish) → P4 (опционально)
>
> Принцип: сначала страховка (тесты + мелкие фиксы), потом рефакторинг. Не чинить «форму» без покрытия.

---

## P0 — Реальные риски сборки / деплоя ✅

### 1. Dockerfile бота: зависимости не из pyproject.toml ✅
**Сделано**: packaging (`py-modules`) в `bot/pyproject.toml`; Dockerfile ставит пакет через `pip install .` после копирования модулей.
**Также**: `backend/Dockerfile` копирует `app/` до `pip install .` (раньше `-e .` шёл до исходников).

### 2. Добавить `.dockerignore` ✅
**Сделано**: `backend/.dockerignore`, `bot/.dockerignore`, `frontend/.dockerignore`.

---

## P1 — Надёжность (делать до крупного рефакторинга) ✅

### 3. Прогнать и закрепить существующие тесты как smoke ✅
**Сделано**: `pytest` — зелёный smoke (`test_api_auth`, `test_security`, `test_llm_factory`).
**Прогон**: `cd backend && .venv/bin/pytest`

### 4. Тесты RecommendationService + Goal CRUD ✅
**Сделано**:
  - `tests/test_recommendation_service.py` — мок LLM: генерация, cooldown, пустые goals, `force`
  - `tests/test_goals_crud.py` — API CRUD на in-memory SQLite (+ past date / 404)
  - `tests/conftest.py` — общий client с override `get_db`
**Dev-зависимости**: `aiosqlite`, `[tool.pytest.ini_options]`

### 5. Мелкие правки без «архитектуры» ✅
**5a.** ✅ `format_recommendation` импортируется наверху `bot/main.py`
**5b.** ✅ `from sqlalchemy import text` в `backend/app/main.py`
**5c.** ✅ `APIClientMiddleware` вынесен в `bot/middleware.py`
**5d.** ⏭️ sync `import redis` в `tasks.py` оставлен lazy by design

---

## P2 — Архитектура (после зелёного smoke + базовых тестов) ✅

### 6. Разбить монолитный `router.py` ✅
**Файл**: `backend/app/api/v1/router.py` (~391 строка)
**Решение**: подроутеры `auth`, `garmin`, `goals`, `stats`, `recommendations`, `health` + сборка в `__init__.py` / `router.py`.
**Сделано**: подроутеры вынесены в `backend/app/api/v1/routes/`; `router.py` теперь агрегирует доменные роутеры.
**Проверка**: `cd backend && .venv/bin/pytest` — зелёный.
**Трудоёмкость**: ~1–1.5 ч

### 7. Разбить `models/__init__.py` и `schemas/__init__.py` ✅
**Решение**: по доменам (`user`, `goal`, `garmin`, `activity`, `recommendation`, …); `__init__.py` реэкспортирует для совместимости (alembic, импорты).
**Сделано**: модели и схемы разнесены по доменным модулям; `__init__.py` оставлены как совместимые реэкспорты.
**Проверка**: `cd backend && .venv/bin/pytest`; `cd backend && .venv/bin/ruff check app/api app/models app/schemas app/services/ai`.
**Трудоёмкость**: ~2–3 ч

---

## P3 — Улучшения продукта / UX ✅

### 8. Frontend: error states + retry ✅
**Файлы**: `frontend/src/app/**/page.tsx`
**Проблема**: при ошибке API — пусто / null.
**Сделано**: страницы целей, статистики и рекомендаций показывают понятное сообщение и кнопку повтора.
**Трудоёмкость**: ~30–40 мин

### 9. Мягкий redirect при 401 ✅
**Файл**: `frontend/src/lib/api.ts`
**Сделано**: сессия очищается, показывается уведомление, редирект на вход происходит с короткой задержкой.
**Трудоёмкость**: ~15 мин

### 10. Loading UI ✅
**Сделано**: добавлен общий `LoadingSpinner` и подключён на страницах данных.
**Трудоёмкость**: ~20 мин

### 11. Request ID middleware ✅
**Файл**: `backend/app/api/middleware.py` (новый)
**Сделано**: `X-Request-ID` берётся из заголовка или генерируется, кладётся в `contextvars` и возвращается в ответе.
**Трудоёмкость**: ~20–30 мин

### 12. Валидация Garmin credentials на входе ✅
**Файл**: схемы / `connect` flow
**Сделано**: `GarminConnectRequest` валидирует формат email и минимальную длину пароля до вызова Garmin API.
**Трудоёмкость**: ~10–15 мин

### 13. Retry при невалидном JSON от LLM ✅
**Файл**: `backend/app/services/ai/common.py`
**Сделано**: общий helper делает до 3 попыток и просит LLM вернуть валидный JSON; затем использует fallback.
**Трудоёмкость**: ~20–30 мин

### 14. GeminiProvider — async SDK (низкий приоритет) ⏭️
**Файл**: `backend/app/services/ai/gemini.py`
**Проблема**: sync `genai.Client` + `asyncio.to_thread()`.
**Решение**: актуальный async API `google-genai` (проверить docs; не `Clinet`).
**Когда**: только если Gemini реально используется; основной путь — Groq/OpenRouter/Ollama.
**Статус**: оставлено по условию плана; GeminiProvider подключён к общему JSON retry, но sync SDK не менялся без подтверждённой необходимости Gemini.
**Трудоёмкость**: ~20–40 мин

---

## P4 — Опционально / с оговорками

### 15. Кэширование LLM-ответов — только с безопасным ключом
**Проблема**: одинаковый промпт ≠ безопасно переиспользовать ответ между пользователями/днями.
**Решение (если делать)**:
  - ключ: `user_id` + дата/окно контекста + hash(промпт) + версия промпта;
  - TTL короткий; явная инвалидация при новом sync Garmin;
  - без этого пункта **не внедрять** — устаревший совет хуже отсутствия кэша.
**Трудоёмкость**: ~1 ч (с тестами на изоляцию ключа)

### 16. Тесты бота / фронта / rate limit
| Что | Подход | Оценка |
|---|---|---|
| Bot handlers | aiogram TestClient / мок API | ~1–1.5 ч |
| Frontend | jest/rtl — загрузка/ошибки | ~1.5–2 ч |
| Rate limiting | httpx, достижение лимита | ~20 мин |
| Garmin sync | мок provider + БД | ~1–1.5 ч |

### 17. Отложить или не делать без явной нужды
- Пустые `__init__.py` во всех подпакетах — почти noop при `PYTHONPATH=/app` / namespace packages.
- `React.StrictMode` в layout — в App Router часто уже включён в dev; низкая ценность.
- Runtime Zod на все ответы API — тяжело; точечно на критичные контракты, если болит.
- SEO `generateMetadata` — дашборд за логином, низкий ROI.

### 18. Безопасность (отдельный трек, не «code style»)
Уже зафиксировано в README: `INTERNAL_BOT_SECRET` даёт доступ к данным любого пользователя при утечке.
**Возможные follow-up** (не смешивать с hygiene-рефакторингом):
  - ротация секрета, отдельный bot identity, аудит логов доступа;
  - не светить postgres default password за пределы local compose;
  - review MFA pending payload в Redis (TTL, scope).
**Известный gap (не закрыт в P0)**: `.env.example` с `localhost` для Postgres/Redis/API ломает `docker compose` без override хостов сервисов — поправить при работе над compose/README.
**Трудоёмкость**: оценка отдельно после threat-model / нужд production.

---

## Порядок выполнения (рекомендуемый)

```
Фаза 1 — Сборка (P0) ✅
  └→ 1. bot Dockerfile + packaging
  └→ 2. .dockerignore (+ backend Dockerfile install)

Фаза 2 — Страховка (P1) ✅
  └→ 3. smoke существующих тестов
  └→ 4. RecommendationService + Goal CRUD
  └→ 5. мелкие правки (5a–5c; 5d оставлен lazy)

Фаза 3 — Архитектура (P2) ← следующее
  └→ 6. split router → прогон тестов
  └→ 7. split models/schemas → прогон тестов

Фаза 4 — Продукт (P3)
  └→ 8 error states → 9 soft 401 → 10 loading
  └→ 11 request ID → 12 garmin validation → 13 LLM JSON retry
  └→ 14 Gemini async — только если нужен

Фаза 5 — По необходимости (P4)
  └→ 15 LLM cache (только с безопасным ключом)
  └→ 16 доп. тесты
  └→ 18 security follow-up / compose hostnames для production
```

---

## Оценка времени

| Фаза | Часы (реалистично) | Статус |
|---|---|---|
| P0 | ~0.5 | ✅ |
| P1 | ~2–2.5 | ✅ |
| P2 | ~3–4.5 | открыто |
| P3 | ~2–2.5 | открыто |
| P4 | ~4–7 (выборочно) | открыто |
| **Осталось (P2–P3)** | **~5–7 ч** | |
| **С выбранным P4** | **~9–14 ч** | |

---

## Что сознательно снято с «критичного»

| Было | Почему снижено |
|---|---|
| Hardcode deps бота как P0 «баг» | Сейчас deps совпадают; риск — drift и хрупкий `-e .` без packaging |
| «Цикл» import `format_recommendation` | Цикла нет; достаточно top-level import |
| sync redis import в worker | Часто lazy by design |
| Пустые `__init__.py`, StrictMode, SEO, Zod everywhere | Низкий ROI |
| LLM cache без оговорок | Риск устаревших/чужих советов |
| Тесты «в конце опционально» | Перед split router/models — обязательный smoke |
