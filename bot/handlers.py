import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api_client import APIClient
from keyboards import (
    DISTANCE_LABELS,
    distance_keyboard,
    goals_list_keyboard,
    main_menu,
    refresh_recommendation_keyboard,
    settings_menu,
    time_keyboard,
)
from states import GarminConnectStates, GoalCreateStates

logger = logging.getLogger(__name__)
router = Router()


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_recommendation(rec: dict) -> str:
    parsed = rec.get("parsed")
    if parsed:
        lines = [f"📋 *{parsed.get('summary', '')}*", "", f"🏃 Сегодня: {parsed.get('today_recommendation', '')}"]
        if parsed.get("progress_to_goal"):
            lines.append(f"\n📈 Прогресс: {parsed['progress_to_goal']}")
        if parsed.get("week_plan"):
            lines.append("\n📅 План на неделю:")
            lines.extend(f"  • {d}" for d in parsed["week_plan"][:7])
        if parsed.get("warnings"):
            lines.append("\n⚠️ Предупреждения:")
            lines.extend(f"  • {w}" for w in parsed["warnings"])
        return "\n".join(lines)
    return rec.get("content", "Нет данных")


@router.message(CommandStart())
async def cmd_start(message: Message, api: APIClient):
    await api.upsert_user(message.from_user.id)
    await message.answer(
        "👋 Добро пожаловать в *AIRun* — ваш AI-тренер для бега!\n\n"
        "Подключите Garmin Connect в настройках, поставьте цель и получайте персональные рекомендации.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer("Настройки:", reply_markup=settings_menu())


@router.message(F.text == "◀️ Назад")
async def back_to_main(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu())


@router.message(F.text == "🔗 Подключить Garmin")
async def garmin_connect_start(message: Message, state: FSMContext):
    await state.set_state(GarminConnectStates.email)
    await message.answer("Введите email от Garmin Connect:")


@router.message(GarminConnectStates.email)
async def garmin_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await state.set_state(GarminConnectStates.password)
    await message.answer("Введите пароль Garmin Connect:")


@router.message(GarminConnectStates.password)
async def garmin_password(message: Message, state: FSMContext, api: APIClient):
    data = await state.get_data()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await message.answer("Подключаю Garmin...")
    try:
        result = await api.garmin_connect(message.from_user.id, data["email"], message.text)
        if result.get("status") == "mfa_required":
            await state.set_state(GarminConnectStates.mfa)
            await message.answer("Введите код MFA из приложения Garmin:")
            return
        await state.clear()
        await message.answer(f"✅ {result.get('message', 'Подключено')}", reply_markup=main_menu())
    except Exception as exc:
        await state.clear()
        await message.answer(f"❌ Ошибка: {exc}", reply_markup=main_menu())


@router.message(GarminConnectStates.mfa)
async def garmin_mfa(message: Message, state: FSMContext, api: APIClient):
    result = await api.garmin_mfa(message.from_user.id, message.text.strip())
    await state.clear()
    if result.get("status") == "connected":
        await message.answer(f"✅ {result['message']}", reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result.get('message', 'Ошибка MFA')}", reply_markup=main_menu())


@router.message(F.text == "❌ Отключить Garmin")
async def garmin_disconnect(message: Message, api: APIClient):
    await api.garmin_disconnect(message.from_user.id)
    await message.answer("Garmin отключён.", reply_markup=settings_menu())


@router.message(F.text == "🎯 Мои цели")
async def list_goals(message: Message, api: APIClient):
    goals = await api.list_goals(message.from_user.id)
    if not goals:
        await message.answer(
            "У вас пока нет целей.",
            reply_markup=goals_list_keyboard([]),
        )
        return
    lines = []
    for g in goals:
        dist = DISTANCE_LABELS.get(g["distance"], g["distance"])
        time_str = format_duration(g.get("target_time_seconds")) if g.get("target_time_seconds") else "финиш"
        lines.append(f"• {dist} — {g['race_date']} ({time_str}), осталось {g['days_until_race']} дн.")
    await message.answer("\n".join(lines), reply_markup=goals_list_keyboard(goals))


@router.callback_query(F.data == "goal_new")
async def goal_new(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GoalCreateStates.distance)
    await callback.message.answer("Выберите дистанцию:", reply_markup=distance_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("goal_dist:"))
async def goal_distance(callback: CallbackQuery, state: FSMContext):
    distance = callback.data.split(":")[1]
    await state.update_data(distance=distance)
    await state.set_state(GoalCreateStates.time_choice)
    await callback.message.answer("Укажите целевое время:", reply_markup=time_keyboard())
    await callback.answer()


@router.callback_query(F.data == "goal_time:none")
async def goal_time_none(callback: CallbackQuery, state: FSMContext):
    await state.update_data(target_time_seconds=None)
    await state.set_state(GoalCreateStates.race_date)
    await callback.message.answer("Введите дату забега (ДД.ММ.ГГГГ):")
    await callback.answer()


@router.callback_query(F.data == "goal_time:custom")
async def goal_time_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GoalCreateStates.time_input)
    await callback.message.answer("Введите целевое время в формате ЧЧ:ММ:СС (например 1:45:00):")
    await callback.answer()


@router.message(GoalCreateStates.time_input)
async def goal_time_input(message: Message, state: FSMContext):
    match = re.match(r"^(\d+):(\d{2}):(\d{2})$", message.text.strip())
    if not match:
        await message.answer("Неверный формат. Используйте ЧЧ:ММ:СС")
        return
    h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
    await state.update_data(target_time_seconds=h * 3600 + m * 60 + s)
    await state.set_state(GoalCreateStates.race_date)
    await message.answer("Введите дату забега (ДД.ММ.ГГГГ):")


@router.message(GoalCreateStates.race_date)
async def goal_race_date(message: Message, state: FSMContext, api: APIClient):
    try:
        race_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return
    data = await state.get_data()
    await api.create_goal(
        message.from_user.id,
        data["distance"],
        race_date,
        data.get("target_time_seconds"),
    )
    await state.clear()
    dist = DISTANCE_LABELS.get(data["distance"], data["distance"])
    await message.answer(f"✅ Цель создана: {dist} — {race_date.strftime('%d.%m.%Y')}", reply_markup=main_menu())


@router.callback_query(F.data.startswith("goal_del:"))
async def goal_delete(callback: CallbackQuery, api: APIClient):
    goal_id = callback.data.split(":")[1]
    await api.delete_goal(callback.from_user.id, goal_id)
    goals = await api.list_goals(callback.from_user.id)
    await callback.message.edit_text("Цель удалена.", reply_markup=goals_list_keyboard(goals))
    await callback.answer()


@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def stats(message: Message, api: APIClient):
    today = await api.stats_today(message.from_user.id)
    week = await api.stats_week(message.from_user.id)
    lines = ["📊 *Статистика*", ""]
    if today and today.get("stats"):
        stats_data = today["stats"]
        lines.append(f"*Сегодня ({today['summary_date']}):*")
        if "totalSteps" in stats_data:
            lines.append(f"  Шаги: {stats_data['totalSteps']}")
        if "totalKilometers" in stats_data:
            lines.append(f"  Дистанция: {stats_data['totalKilometers']} км")
    lines.append("")
    lines.append(f"*За неделю:*")
    lines.append(f"  Пробежек: {week['activity_count']}")
    lines.append(f"  Дистанция: {week['total_distance_m'] / 1000:.1f} км")
    lines.append(f"  Время: {format_duration(week['total_duration_sec'])}")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(F.text == "💡 Рекомендации")
@router.message(Command("recommendations"))
async def recommendations(message: Message, api: APIClient):
    rec = await api.latest_recommendation(message.from_user.id)
    if not rec:
        await message.answer(
            "Пока нет рекомендаций. Создайте цель и подключите Garmin.",
            reply_markup=refresh_recommendation_keyboard(),
        )
        return
    await message.answer(
        format_recommendation(rec),
        parse_mode="Markdown",
        reply_markup=refresh_recommendation_keyboard(),
    )


@router.callback_query(F.data == "rec_refresh")
async def rec_refresh(callback: CallbackQuery, api: APIClient):
    await callback.message.answer("Генерирую рекомендации...")
    result = await api.generate_recommendation(callback.from_user.id, force=True)
    if result.get("success") and result.get("recommendation"):
        await callback.message.answer(
            format_recommendation(result["recommendation"]),
            parse_mode="Markdown",
            reply_markup=refresh_recommendation_keyboard(),
        )
    else:
        await callback.message.answer(result.get("message", "Не удалось сгенерировать"))
    await callback.answer()


@router.message(F.text == "🔄 Синхронизация")
@router.message(Command("sync"))
async def sync(message: Message, api: APIClient):
    await message.answer("Синхронизирую данные Garmin...")
    result = await api.trigger_sync(message.from_user.id)
    if result.get("success"):
        await message.answer(
            f"✅ {result['message']}\n"
            f"Активностей: {result.get('activities_synced', 0)}, "
            f"сводок: {result.get('summaries_synced', 0)}"
        )
    else:
        await message.answer(f"❌ {result.get('message', 'Ошибка синхронизации')}")
