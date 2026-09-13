# План исправлений AIRun

> Приоритет: P0 (блокирует/ломает) → P1 (надёжность) → P2 (архитектура) → P3 (UX/polish) → P4 (опционально)
>
> Принцип: сначала страховка (тесты + мелкие фиксы), потом рефакторинг. Не чинить «форму» без покрытия.

---

## P0 — Реальные риски сборки / деплоя

### 1. Dockerfile бота: зависимости не из pyproject.toml
**Файл**: `bot/Dockerfile:6`, `bot/pyproject.toml`
**Проблема**: hardcoded `pip install aiogram httpx redis pydantic-settings` — drift с `pyproject.toml` при добавлении пакетов.
**Важно**: простой `pip install -e .` сейчас, скорее всего, упадёт — в `bot/pyproject.toml` нет packaging-конфига (`[tool.setuptools.packages.find]` / package layout), в отличие от backend.
**Решение**:
  1. Добавить в `bot/pyproject.toml` setuptools package config (или явный список модулей).
  2. В Dockerfile: `COPY pyproject.toml .` (+ при необходимости исходники) → `RUN pip install --no-cache-dir .` (или `-e .` после полного `COPY`).
  3. Сверить с паттерном `backend/Dockerfile` (там тоже `pip install -e .` до полного `COPY` — проверить, что editable install реально подхватывает пакет).
**Трудоёмкость**: ~20–30 мин

### 2. Добавить `.dockerignore`
**Файлы**: отсутствуют в `backend/`, `bot/`, `frontend/`
**Проблема**: в контекст билда могут попасть `.venv`, `__pycache__`, `.env`, `.next`, тесты/кэш.
**Решение**: `.dockerignore` на каждый сервис (минимум: `.venv`, `__pycache__`, `.env*`, `.git`, `*.pyc`, `node_modules`, `.next`).
**Трудоёмкость**: ~10 мин

---

## P1 — Надёжность (делать до крупного рефакторинга)

### 3. Прогнать и закрепить существующие тесты как smoke
**Файлы**: `backend/tests/test_api_auth.py`, `test_security.py`, `test_llm_factory.py`
**Проблема**: рефакторинг router/models без зелёного smoke — высокий риск регрессий.
**Решение**: убедиться, что тесты стабильно проходят в CI/локально; после каждого шага P2 — прогон.
**Трудоёмкость**: ~15–30 мин

### 4. Тесты RecommendationService + Goal CRUD
**Подход**:
  - RecommendationService: мок LLMProvider — генерация, cooldown, пустые данные
  - Goal CRUD: API-тесты с БД (транзакция / rollback)
**Зачем сейчас**: покрытие перед split `router.py` / models.
**Трудоёмкость**: ~1.5–2 ч

### 5. Мелкие правки без «архитектуры»
**5a. `format_recommendation` в `bot/main.py`**
  - Диагноз «циклическая зависимость» — **ложный**: `main` уже импортирует `from handlers import router`.
  - Решение: импорт наверх файла (`from handlers import router, format_recommendation`). Отдельный util-модуль — только если появится реальный цикл.
  - ~5 мин

**5b. Healthcheck `__import__("sqlalchemy")`**
  - Файл: `backend/app/main.py`
  - Решение: `from sqlalchemy import text` наверху.
  - ~2 мин

**5c. Вынести `APIClientMiddleware` из `main()`**
  - Файл: `bot/main.py` → `bot/middleware.py`
  - Делать, если нужны юнит-тесты middleware; иначе P3.
  - ~10 мин

**5d. sync `import redis` в `tasks.py`**
  - Часто намеренный lazy import для воркера — **не баг**.
  - Переносить наверх только если мешает единообразию; иначе оставить.
  - ~2 мин (если трогать)

---

## P2 — Архитектура (после зелёного smoke + базовых тестов)

### 6. Разбить монолитный `router.py`
**Файл**: `backend/app/api/v1/router.py` (~391 строка)
**Решение**: подроутеры `auth`, `garmin`, `goals`, `stats`, `recommendations`, `health` + сборка в `__init__.py` / `router.py`.
**Обязательно**: прогон тестов после split.
**Трудоёмкость**: ~1–1.5 ч

### 7. Разбить `models/__init__.py` и `schemas/__init__.py`
**Решение**: по доменам (`user`, `goal`, `garmin`, `activity`, `recommendation`, …); `__init__.py` реэкспортирует для совместимости (alembic, импорты).
**Осторожно**: relationships / circular imports между моделями — заложить буфер времени.
**Трудоёмкость**: ~2–3 ч

---

## P3 — Улучшения продукта / UX

### 8. Frontend: error states + retry
**Файлы**: `frontend/src/app/**/page.tsx`
**Проблема**: при ошибке API — пусто / null.
**Решение**: понятное сообщение + кнопка повтора (важнее спиннера).
**Трудоёмкость**: ~30–40 мин

### 9. Мягкий redirect при 401
**Файл**: `frontend/src/lib/api.ts`
**Решение**: toast / уведомление, затем редирект с короткой задержкой (не мгновенная потеря контекста).
**Трудоёмкость**: ~15 мин

### 10. Loading UI
**Решение**: общий `LoadingSpinner` вместо сырого «Загрузка...» — polish, после error states.
**Трудоёмкость**: ~20 мин

### 11. Request ID middleware
**Файл**: `backend/app/api/middleware.py` (новый)
**Решение**: `X-Request-ID` (из заголовка или generate) → contextvars / логи.
**Трудоёмкость**: ~20–30 мин

### 12. Валидация Garmin credentials на входе
**Файл**: схемы / `connect` flow
**Решение**: Pydantic — формат email, min length password — до вызова Garmin API.
**Трудоёмкость**: ~10–15 мин

### 13. Retry при невалидном JSON от LLM
**Файл**: `backend/app/services/ai/common.py`
**Решение**: 1–2 повторных запроса с просьбой исправить JSON; затем fallback.
**Трудоёмкость**: ~20–30 мин

### 14. GeminiProvider — async SDK (низкий приоритет)
**Файл**: `backend/app/services/ai/gemini.py`
**Проблема**: sync `genai.Client` + `asyncio.to_thread()`.
**Решение**: актуальный async API `google-genai` (проверить docs; не `Clinet`).
**Когда**: только если Gemini реально используется; основной путь — Groq/OpenRouter/Ollama.
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
**Трудоёмкость**: оценка отдельно после threat-model / нужд production.

---

## Порядок выполнения (рекомендуемый)

```
Фаза 1 — Сборка (P0)
  └→ 1. bot Dockerfile + packaging
  └→ 2. .dockerignore (+ проверка backend Dockerfile install)

Фаза 2 — Страховка (P1)
  └→ 3. smoke существующих тестов
  └→ 4. RecommendationService + Goal CRUD
  └→ 5. мелкие правки (5a–5b обязательно; 5c–5d по желанию)

Фаза 3 — Архитектура (P2)
  └→ 6. split router → прогон тестов
  └→ 7. split models/schemas → прогон тестов

Фаза 4 — Продукт (P3)
  └→ 8 error states → 9 soft 401 → 10 loading
  └→ 11 request ID → 12 garmin validation → 13 LLM JSON retry
  └→ 14 Gemini async — только если нужен

Фаза 5 — По необходимости (P4)
  └→ 15 LLM cache (только с безопасным ключом)
  └→ 16 доп. тесты
  └→ 18 security follow-up для production
```

---

## Оценка времени

| Фаза | Часы (реалистично) |
|---|---|
| P0 | ~0.5 |
| P1 | ~2–2.5 |
| P2 | ~3–4.5 |
| P3 | ~2–2.5 |
| P4 | ~4–7 (выборочно) |
| **MVP плана (P0–P3 без Gemini/кэша)** | **~8–10 ч** |
| **С выбранным P4** | **~12–17 ч** |

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
