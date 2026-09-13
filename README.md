# AIRun — Garmin + AI Running Coach

Система сбора данных с Garmin Connect, AI-рекомендаций для бегунов и Telegram-бота как основного интерфейса.

## Быстрый старт

```bash
cp .env.example .env
# Заполните обязательные переменные (см. ниже)

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build
```

Сервисы:
- API: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Telegram-бот: основной интерфейс

## Обязательные переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота |
| `TELEGRAM_BOT_USERNAME` | Username бота без @ (для Login Widget) |
| `INTERNAL_BOT_SECRET` | Секрет bot→API (заголовки `X-Internal-Bot-Secret` + `X-Bot-Telegram-Id`) |
| `JWT_SECRET` | Ключ для подписи JWT web-сессий (обязателен) |
| `CREDENTIALS_ENCRYPTION_KEY` | Fernet-ключ для токенов Garmin |
| `CORS_ORIGINS` | Разрешённые origins для frontend (через запятую) |

### AI-провайдер (рекомендации)

По умолчанию `LLM_PROVIDER=auto` — выбирается первый настроенный провайдер, при ошибке пробует следующий.

| Провайдер | Ключ | Плюсы | Как получить |
|---|---|---|---|
| **Groq** (рекомендуется) | `GROQ_API_KEY` | Бесплатный tier, быстрый Llama 3.3 70B | [console.groq.com](https://console.groq.com) |
| **OpenRouter** | `OPENROUTER_API_KEY` | Один ключ, много моделей, есть `:free` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Ollama** | без ключа | Полностью локально, приватно | [ollama.com](https://ollama.com) + `OLLAMA_ENABLED=true` |
| **Gemini** | `GEMINI_API_KEY` | Опционально, если доступен AI Studio | [aistudio.google.com](https://aistudio.google.com) |

Минимальная настройка без Gemini:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

Для Ollama в Docker на Mac/Windows:

```bash
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=llama3.2
```

## Безопасность

- **API**: все эндпоинты (кроме `/health`, `/ready`, `/auth/telegram-web`) требуют:
  - `X-Internal-Bot-Secret` + `X-Bot-Telegram-Id` (должен совпадать с `telegram_id` в query) — для бота, или
  - `Authorization: Bearer <JWT>` — для web-дашборда
- **Важно:** храните `INTERNAL_BOT_SECRET` только в bot/api контейнерах; при утечке возможен доступ к данным любого пользователя
- **MFA-сессии**: пароль Garmin шифруется Fernet перед сохранением в Redis
- **Frontend**: вход только через Telegram Login Widget с верификацией hash на backend

## Disclaimer — Garmin Connect

Неофициальный доступ через `python-garminconnect`. Используйте на свой риск. Для production — официальный Garmin Connect Developer Program.

## Структура

```
AIRun/
├── backend/     # FastAPI + Celery
├── bot/         # Telegram bot (aiogram)
├── frontend/    # Next.js dashboard
└── docker-compose.yml
```
