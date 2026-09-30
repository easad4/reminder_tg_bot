from calendar import monthrange
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
             "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
WEEKDAYS_RU = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


def build_calendar(year: int, month: int, prefix: str = "cal") -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    kb.append([InlineKeyboardButton(text=f"{MONTHS_RU[month-1]} {year}", callback_data="ignore")])
    kb.append([InlineKeyboardButton(text=d, callback_data="ignore") for d in WEEKDAYS_RU])

    first_weekday, days_in_month = monthrange(year, month)  # 0 = Monday
    row: list[InlineKeyboardButton] = []
    for _ in range(first_weekday):
        row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
    for day in range(1, days_in_month + 1):
        row.append(InlineKeyboardButton(
            text=str(day),
            callback_data=f"{prefix}:{year}-{month:02d}-{day:02d}",
        ))
        if len(row) == 7:
            kb.append(row)
            row = []
    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        kb.append(row)

    if month == 1:
        prev_y, prev_m = year - 1, 12
    else:
        prev_y, prev_m = year, month - 1
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1

    kb.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_nav:{prev_y}-{prev_m:02d}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
        InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_nav:{next_y}-{next_m:02d}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)