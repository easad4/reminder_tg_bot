import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states.task_states import CreateTask
from keyboards.main import (
    cancel_kb, back_cancel_kb, priority_kb, remind_kb,
    hours_kb, minutes_kb, confirm_kb, main_menu,
)
from keyboards.calendar import build_calendar
from services import tasks as tasks_service
from services import reminders as reminders_service
from services import users as users_service

log = logging.getLogger(__name__)
router = Router()

PRIORITY_LABEL = {"low": "🟢 Низкий", "medium": "🟡 Средний", "high": "🔴 Высокий"}
REMIND_LABEL = {1440: "За день", 60: "За час", 15: "За 15 минут", 0: "Точно в срок"}


def _local_dt(data: dict, tz_name: str) -> datetime | None:
    if not data.get("date") or not data.get("time"):
        return None
    y, m, d = map(int, data["date"].split("-"))
    hh, mm = map(int, data["time"].split(":"))
    return datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))


def _preview(data: dict, tz_name: str) -> str:
    dt = _local_dt(data, tz_name)
    due = dt.strftime("%d.%m.%Y %H:%M") if dt else "—"
    lines = [
        "🧾 <b>Проверьте задачу</b>\n",
        f"📌 <b>{data.get('title','—')}</b>",
    ]
    if data.get("description"):
        lines.append(f"📝 {data['description']}")
    lines.append(f"🗓 {due} ({tz_name})")
    lines.append(f"⚡ Приоритет: {PRIORITY_LABEL.get(data.get('priority','medium'))}")
    lines.append(f"🔔 Напоминание: {REMIND_LABEL.get(data.get('remind_before',0), '—')}")
    return "\n".join(lines)


@router.message(F.text == "➕ Создать задачу")
async def start_create(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data()
    await state.set_state(CreateTask.title)
    await message.answer(
        "Шаг 1/6. Введите <b>название</b> задачи:",
        reply_markup=cancel_kb(),
    )


@router.message(CreateTask.title, F.text)
async def step_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 2 or len(title) > 200:
        await message.answer("Название должно быть от 2 до 200 символов. Попробуйте снова.")
        return
    await state.update_data(title=title)
    await state.set_state(CreateTask.description)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="ct_skip")],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="ct_back:title"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="create_cancel"),
        ],
    ])
    await message.answer("Шаг 2/6. Введите <b>описание</b> или нажмите «Пропустить»:", reply_markup=kb)


@router.callback_query(F.data == "ct_skip")
async def step_skip_desc(cb: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(CreateTask.date)
    now = datetime.now()
    await cb.message.edit_text(
        "Шаг 3/6. Выберите <b>дату</b>:",
        reply_markup=build_calendar(now.year, now.month, prefix="cal"),
    )
    await cb.answer()


@router.message(CreateTask.description, F.text)
async def step_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip() or None)
    await state.set_state(CreateTask.date)
    now = datetime.now()
    await message.answer(
        "Шаг 3/6. Выберите <b>дату</b>:",
        reply_markup=build_calendar(now.year, now.month, prefix="cal"),
    )


@router.callback_query(F.data == "ignore")
async def ignore_cb(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("cal_nav:"))
async def cal_nav(cb: CallbackQuery, state: FSMContext):
    y, m = map(int, cb.data.split(":")[1].split("-"))
    await cb.message.edit_reply_markup(reply_markup=build_calendar(y, m, prefix="cal"))
    await cb.answer()


@router.callback_query(F.data.startswith("cal:"))
async def cal_pick(cb: CallbackQuery, state: FSMContext):
    date_str = cb.data.split(":", 1)[1]
    await state.update_data(date=date_str)
    await state.set_state(CreateTask.time_h)
    await cb.message.edit_text("Шаг 4/6. Выберите <b>час</b>:", reply_markup=hours_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ct_h:"))
async def pick_hour(cb: CallbackQuery, state: FSMContext):
    h = int(cb.data.split(":")[1])
    await state.update_data(hour=h)
    await state.set_state(CreateTask.time_m)
    await cb.message.edit_text(f"Час: <b>{h:02d}</b>. Выберите <b>минуты</b>:", reply_markup=minutes_kb(h))
    await cb.answer()


@router.callback_query(F.data.startswith("ct_m:"))
async def pick_minute(cb: CallbackQuery, state: FSMContext):
    _, h, m = cb.data.split(":")
    h, m = int(h), int(m)
    await state.update_data(time=f"{h:02d}:{m:02d}")
    await state.set_state(CreateTask.priority)
    await cb.message.edit_text("Шаг 5/6. Выберите <b>приоритет</b>:", reply_markup=priority_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ct_pri:"))
async def pick_priority(cb: CallbackQuery, state: FSMContext):
    p = cb.data.split(":")[1]
    if p not in ("low", "medium", "high"):
        await cb.answer("Некорректный приоритет", show_alert=True)
        return
    await state.update_data(priority=p)
    await state.set_state(CreateTask.remind)
    await cb.message.edit_text("Шаг 6/6. Когда <b>напомнить</b>?", reply_markup=remind_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ct_rem:"))
async def pick_remind(cb: CallbackQuery, state: FSMContext):
    rb = int(cb.data.split(":")[1])
    await state.update_data(remind_before=rb)
    await state.set_state(CreateTask.confirm)
    data = await state.get_data()
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    await cb.message.edit_text(_preview(data, tz_name), reply_markup=confirm_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("ct_back:"))
async def back_step(cb: CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    data = await state.get_data()
    if target == "title":
        await state.set_state(CreateTask.title)
        await cb.message.edit_text("Шаг 1/6. Введите <b>название</b> задачи:", reply_markup=cancel_kb())
    elif target == "date":
        await state.set_state(CreateTask.date)
        now = datetime.now()
        await cb.message.edit_text("Шаг 3/6. Выберите <b>дату</b>:",
                                   reply_markup=build_calendar(now.year, now.month, prefix="cal"))
    elif target == "time":
        await state.set_state(CreateTask.time_h)
        await cb.message.edit_text("Шаг 4/6. Выберите <b>час</b>:", reply_markup=hours_kb())
    elif target == "priority":
        await state.set_state(CreateTask.priority)
        await cb.message.edit_text("Шаг 5/6. Выберите <b>приоритет</b>:", reply_markup=priority_kb())
    elif target == "remind":
        await state.set_state(CreateTask.remind)
        await cb.message.edit_text("Шаг 6/6. Когда <b>напомнить</b>?", reply_markup=remind_kb())
    await cb.answer()


@router.callback_query(F.data == "ct_save")
async def save_task(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"

    dt_local = _local_dt(data, tz_name)
    if dt_local is None:
        await cb.answer("Некорректные дата/время", show_alert=True)
        return
    due_utc = dt_local.astimezone(timezone.utc)
    if due_utc <= datetime.now(timezone.utc):
        await cb.answer("Нельзя создать задачу в прошлом", show_alert=True)
        return
    if not data.get("title"):
        await cb.answer("Нет названия", show_alert=True)
        return

    task_id, reminder_id, fire_at = await tasks_service.create_task(
        user_id=cb.from_user.id,
        title=data["title"],
        description=data.get("description"),
        due_utc=due_utc,
        priority=data.get("priority", "medium"),
        remind_before=int(data.get("remind_before", 0)),
    )
    reminders_service.schedule_reminder(reminder_id, fire_at)

    await state.clear()
    await cb.message.edit_text(f"✅ Задача сохранена (id {task_id}).")
    await cb.message.answer("Главное меню:", reply_markup=main_menu())
    await cb.answer("Сохранено")


@router.callback_query(F.data == "create_cancel")
async def cancel_create(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Создание отменено.")
    await cb.message.answer("Главное меню:", reply_markup=main_menu())
    await cb.answer()