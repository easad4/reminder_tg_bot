from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from keyboards.main import (
    task_actions_kb, confirm_delete_kb, postpone_kb, edit_fields_kb,
    priority_kb, main_menu,
)
from keyboards.calendar import build_calendar
from services import tasks as tasks_service
from services import reminders as reminders_service
from services import users as users_service
from states.task_states import EditTask

router = Router()


def _card(row, tz_name: str) -> str:
    from services.tasks import PRIORITY_EMOJI, PRIORITY_NAME, _parse
    due_local = _parse(row["due_utc"]).astimezone(ZoneInfo(tz_name))
    emoji = PRIORITY_EMOJI.get(row["priority"], "🟡")
    prio = PRIORITY_NAME.get(row["priority"], "средний")
    text = f"📌 <b>{row['title']}</b>\n🗓 {due_local.strftime('%d.%m.%Y %H:%M')}\n{emoji} {prio}"
    if row["description"]:
        text += f"\n📝 {row['description']}"
    if row["status"] == "done":
        text = "✅ <i>Выполнено</i>\n\n" + text
    return text


async def _show_task(cb: CallbackQuery, task_id: int):
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return None
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    await cb.message.edit_text(_card(task, tz_name), reply_markup=task_actions_kb(task_id))
    return task


@router.callback_query(F.data.startswith("t:view:"))
async def view_task(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[2])
    await _show_task(cb, task_id)
    await cb.answer()


@router.callback_query(F.data.startswith("t:done:"))
async def done_task(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[2])
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return
    ok = await tasks_service.mark_done(task_id, cb.from_user.id)
    if ok and task["repeat_rule"]:
        await tasks_service.create_next_repeat(task)
    await cb.answer("Готово ✅")
    try:
        await cb.message.edit_text("✅ Задача выполнена.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("t:del:"))
async def del_task(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[2])
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return
    await cb.message.edit_text(
        f"🗑 Удалить задачу «{task['title']}»?",
        reply_markup=confirm_delete_kb(task_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("t:delc:"))
async def del_confirm(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[2])
    ok = await tasks_service.delete_task(task_id, cb.from_user.id)
    await cb.message.edit_text("🗑 Удалено." if ok else "Задача не найдена.")
    await cb.answer()


@router.callback_query(F.data.startswith("t:post:"))
async def postpone_menu(cb: CallbackQuery):
    parts = cb.data.split(":")
    task_id = int(parts[2])
    if len(parts) == 3:
        await cb.message.edit_text("⏰ На сколько отложить?", reply_markup=postpone_kb(task_id))
        await cb.answer()
        return
    minutes = int(parts[3])
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return
    new_due = tasks_service._parse(task["due_utc"]) + timedelta(minutes=minutes)
    await tasks_service.update_task(task_id, cb.from_user.id, due_utc=new_due)
    rid, fire_at = await tasks_service.reschedule_reminder(
        task_id, cb.from_user.id, new_due, task["remind_before"]
    )
    reminders_service.schedule_reminder(rid, fire_at)
    await cb.answer(f"Отложено на {minutes} мин")
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    await cb.message.edit_text(_card(task, tz_name), reply_markup=task_actions_kb(task_id))


@router.callback_query(F.data.startswith("t:edit:"))
async def edit_menu(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[2])
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return
    await cb.message.edit_text("📝 Что редактируем?", reply_markup=edit_fields_kb(task_id))
    await cb.answer()


@router.callback_query(F.data.startswith("t:editf:"))
async def edit_field(cb: CallbackQuery, state: FSMContext):
    _, _, task_id, field = cb.data.split(":")
    task_id = int(task_id)
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    if task is None:
        await cb.answer("Задача не найдена", show_alert=True)
        return

    if field == "priority":
        await state.set_state(EditTask.waiting_value)
        await state.update_data(edit_task_id=task_id, edit_field="priority")
        await cb.message.edit_text("Выберите новый приоритет:",
                                   reply_markup=priority_kb(prefix=f"ep_{task_id}"))
        await cb.answer()
        return

    if field == "due":
        await state.set_state(EditTask.waiting_value)
        await state.update_data(edit_task_id=task_id, edit_field="due_date")
        now = datetime.now()
        await cb.message.edit_text("Выберите новую дату:",
                                   reply_markup=build_calendar(now.year, now.month, prefix=f"ecal_{task_id}"))
        await cb.answer()
        return

    await state.set_state(EditTask.waiting_value)
    await state.update_data(edit_task_id=task_id, edit_field=field)
    label = {"title": "название", "description": "описание"}.get(field, field)
    await cb.message.edit_text(
        f"Введите новое {label} (или отправьте «-», чтобы очистить):"
    )
    await cb.answer()


@router.callback_query(F.data.regexp(r"^ep_\d+:(low|medium|high)$"))
async def edit_priority_cb(cb: CallbackQuery, state: FSMContext):
    prefix, value = cb.data.split(":")
    task_id = int(prefix.split("_")[1])
    await tasks_service.update_task(task_id, cb.from_user.id, priority=value)
    await state.clear()
    task = await tasks_service.get_task(task_id, cb.from_user.id)
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    await cb.message.edit_text(_card(task, tz_name), reply_markup=task_actions_kb(task_id))
    await cb.answer("Обновлено")


@router.callback_query(F.data.startswith("ecal_"))
async def edit_cal_pick(cb: CallbackQuery, state: FSMContext):
    # ecal_{task_id}:YYYY-MM-DD
    prefix, date_str = cb.data.split(":", 1)
    task_id = int(prefix.split("_")[1])
    await state.update_data(edit_task_id=task_id, edit_field="due_date", edit_date=date_str)
    await cb.message.edit_text(
        f"Дата: <b>{date_str}</b>. Введите время в формате ЧЧ:ММ (например 15:30):"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ecal_nav_"))
async def edit_cal_nav(cb: CallbackQuery, state: FSMContext):
    # ecal_nav_{task_id}:YYYY-MM
    prefix, ym = cb.data.split(":", 1)
    task_id = int(prefix.split("_")[2])
    y, m = map(int, ym.split("-"))
    await cb.message.edit_reply_markup(reply_markup=build_calendar(y, m, prefix=f"ecal_{task_id}"))
    await cb.answer()


@router.message(EditTask.waiting_value, F.text)
async def edit_value(message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    field = data.get("edit_field")
    if not task_id:
        await state.clear()
        return
    value = message.text.strip()
    if value == "-":
        value = None

    if field == "due_date":
        try:
            hh, mm = map(int, value.split(":"))
            y, mo, d = map(int, data["edit_date"].split("-"))
            dt_local = datetime(y, mo, d, hh, mm, tzinfo=ZoneInfo("UTC"))
            user = await users_service.get_user(message.from_user.id)
            tz_name = user["timezone"] if user else "Europe/Moscow"
            dt_local = datetime(y, mo, d, hh, mm, tzinfo=ZoneInfo(tz_name))
            due_utc = dt_local.astimezone(timezone.utc)
        except Exception:
            await message.answer("Неверный формат. Введите ЧЧ:ММ")
            return
        await tasks_service.update_task(task_id, message.from_user.id, due_utc=due_utc)
        task = await tasks_service.get_task(task_id, message.from_user.id)
        rid, fire_at = await tasks_service.reschedule_reminder(
            task_id, message.from_user.id, due_utc, task["remind_before"]
        )
        reminders_service.schedule_reminder(rid, fire_at)
    elif field == "title":
        if not value:
            await message.answer("Название не может быть пустым.")
            return
        await tasks_service.update_task(task_id, message.from_user.id, title=value)
    elif field == "description":
        await tasks_service.update_task(task_id, message.from_user.id, description=value)

    await state.clear()
    task = await tasks_service.get_task(task_id, message.from_user.id)
    user = await users_service.get_user(message.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    await message.answer(_card(task, tz_name), reply_markup=task_actions_kb(task_id))