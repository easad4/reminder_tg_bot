from zoneinfo import ZoneInfo, available_timezones
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from keyboards.main import main_menu
from services import users as users_service
from services import reminders as reminders_service
from states.task_states import SettingsFSM

router = Router()

POPULAR_TZ = [
    "Europe/Kaliningrad", "Europe/Moscow", "Europe/Samara",
    "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Krasnoyarsk",
    "Asia/Irkutsk", "Asia/Yakutsk", "Asia/Vladivostok",
    "Asia/Magadan", "Asia/Kamchatka", "UTC",
]


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set:tz")],
        [InlineKeyboardButton(text="⏰ Время сводки", callback_data="set:digest")],
    ])


def tz_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=tz, callback_data=f"set:tzv:{tz}")] for tz in POPULAR_TZ]
    rows.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="set:tzmanual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "⚙️ Настройки")
async def open_settings(message: Message):
    user = await users_service.get_user(message.from_user.id)
    if user is None:
        await users_service.ensure_user(message.from_user.id)
        user = await users_service.get_user(message.from_user.id)
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🌍 Часовой пояс: <b>{user['timezone']}</b>\n"
        f"⏰ Время сводки: <b>{user['digest_time']}</b>"
    )
    await message.answer(text, reply_markup=settings_kb())


@router.callback_query(F.data == "set:tz")
async def set_tz_menu(cb: CallbackQuery):
    await cb.message.edit_text("Выберите часовой пояс:", reply_markup=tz_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("set:tzv:"))
async def set_tz_value(cb: CallbackQuery):
    tz = cb.data.split(":", 2)[2]
    if tz not in available_timezones():
        await cb.answer("Неизвестный TZ", show_alert=True)
        return
    await users_service.set_timezone(cb.from_user.id, tz)
    user = await users_service.get_user(cb.from_user.id)
    reminders_service.schedule_digest(cb.from_user.id, user["timezone"], user["digest_time"])
    await cb.message.edit_text(f"✅ Часовой пояс: <b>{tz}</b>")
    await cb.answer("Сохранено")


@router.callback_query(F.data == "set:tzmanual")
async def set_tz_manual(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.timezone)
    await cb.message.edit_text("Введите TZ, например Europe/Moscow:")
    await cb.answer()


@router.message(SettingsFSM.timezone, F.text)
async def tz_manual_value(message: Message, state: FSMContext):
    tz = message.text.strip()
    if tz not in available_timezones():
        await message.answer("Такого TZ нет. Пример: Europe/Moscow")
        return
    await users_service.set_timezone(message.from_user.id, tz)
    user = await users_service.get_user(message.from_user.id)
    reminders_service.schedule_digest(message.from_user.id, user["timezone"], user["digest_time"])
    await state.clear()
    await message.answer(f"✅ Часовой пояс: {tz}", reply_markup=main_menu())


@router.callback_query(F.data == "set:digest")
async def set_digest(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFSM.digest)
    await cb.message.edit_text("Введите время сводки в формате ЧЧ:ММ (например 09:00).\n"
                               "Отправьте «off», чтобы отключить.")
    await cb.answer()


@router.message(SettingsFSM.digest, F.text)
async def digest_value(message: Message, state: FSMContext):
    v = message.text.strip().lower()
    if v == "off":
        await users_service.set_digest_time(message.from_user.id, "00:00")
        await state.clear()
        await message.answer("Сводка выключена.", reply_markup=main_menu())
        return
    try:
        hh, mm = map(int, v.split(":"))
        assert 0 <= hh < 24 and 0 <= mm < 60
    except Exception:
        await message.answer("Неверный формат. Пример: 09:00")
        return
    hhmm = f"{hh:02d}:{mm:02d}"
    await users_service.set_digest_time(message.from_user.id, hhmm)
    user = await users_service.get_user(message.from_user.id)
    reminders_service.schedule_digest(message.from_user.id, user["timezone"], hhmm)
    await state.clear()
    await message.answer(f"✅ Время сводки: {hhmm}", reply_markup=main_menu())