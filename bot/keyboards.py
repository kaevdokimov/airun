from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

DISTANCE_LABELS = {
    "5k": "5 км",
    "10k": "10 км",
    "half": "Полумарафон",
    "marathon": "Марафон",
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🎯 Мои цели")],
            [KeyboardButton(text="💡 Рекомендации"), KeyboardButton(text="🔄 Синхронизация")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )


def settings_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Подключить Garmin")],
            [KeyboardButton(text="❌ Отключить Garmin")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def distance_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"goal_dist:{key}")]
        for key, label in DISTANCE_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без целевого времени (финиш)", callback_data="goal_time:none")],
            [InlineKeyboardButton(text="Указать время", callback_data="goal_time:custom")],
        ]
    )


def goals_list_keyboard(goals: list) -> InlineKeyboardMarkup:
    buttons = []
    for g in goals:
        label = f"{DISTANCE_LABELS.get(g['distance'], g['distance'])} — {g['race_date']}"
        buttons.append([InlineKeyboardButton(text=f"🗑 {label}", callback_data=f"goal_del:{g['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ Новая цель", callback_data="goal_new")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def refresh_recommendation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить", callback_data="rec_refresh")]]
    )
