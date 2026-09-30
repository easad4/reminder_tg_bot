from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="➕ Создать задачу")],
            [KeyboardButton(text="📅 Сегодня"),   KeyboardButton(text="⏳ Просроченные")],
            [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )


def cancel_kb(cb: str = "create_cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=cb)]
    ])


def back_cancel_kb(back_cb: str, cancel_cb: str = "create_cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb),
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_cb),
        ]
    ])


def task_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"t:done:{task_id}")],
        [InlineKeyboardButton(text="📝 Редактировать", callback_data=f"t:edit:{task_id}")],
        [InlineKeyboardButton(text="⏰ Отложить", callback_data=f"t:post:{task_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"t:del:{task_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="list:my:0")],
    ])


def confirm_delete_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"t:delc:{task_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"t:view:{task_id}"),
        ]
    ])


def postpone_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+5 мин",  callback_data=f"t:post:{task_id}:5"),
            InlineKeyboardButton(text="+15 мин", callback_data=f"t:post:{task_id}:15"),
        ],
        [
            InlineKeyboardButton(text="+1 час",  callback_data=f"t:post:{task_id}:60"),
            InlineKeyboardButton(text="+1 день", callback_data=f"t:post:{task_id}:1440"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"t:view:{task_id}")],
    ])


def edit_fields_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"t:editf:{task_id}:title")],
        [InlineKeyboardButton(text="Описание", callback_data=f"t:editf:{task_id}:description")],
        [InlineKeyboardButton(text="Дата и время", callback_data=f"t:editf:{task_id}:due")],
        [InlineKeyboardButton(text="Приоритет", callback_data=f"t:editf:{task_id}:priority")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"t:view:{task_id}")],
    ])


def priority_kb(prefix: str = "ct_pri") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Низкий",  callback_data=f"{prefix}:low")],
        [InlineKeyboardButton(text="🟡 Средний", callback_data=f"{prefix}:medium")],
        [InlineKeyboardButton(text="🔴 Высокий", callback_data=f"{prefix}:high")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel")],
    ])


def remind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="За день",     callback_data="ct_rem:1440")],
        [InlineKeyboardButton(text="За час",      callback_data="ct_rem:60")],
        [InlineKeyboardButton(text="За 15 минут", callback_data="ct_rem:15")],
        [InlineKeyboardButton(text="Точно в срок", callback_data="ct_rem:0")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ct_back:priority"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
        ],
    ])


def hours_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for h in range(24):
        row.append(InlineKeyboardButton(text=f"{h:02d}", callback_data=f"ct_h:{h}"))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ct_back:date"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minutes_kb(hour: int) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for m in range(0, 60, 5):
        row.append(InlineKeyboardButton(text=f"{m:02d}", callback_data=f"ct_m:{hour}:{m}"))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="ct_back:time"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="ct_save")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ct_back:remind"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
        ],
    ])