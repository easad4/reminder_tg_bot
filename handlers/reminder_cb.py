from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.main import task_actions_kb
from services import tasks as tasks_service
from services import users as users_service

router = Router()


@router.callback_query(F.data.startswith("rem:snooze:"))
async def rem_snooze(cb: CallbackQuery):
    # дублируем логику отложить из actions.py
    _, _, task_id, minutes = cb.data.split(":")
    task_id, minutes = int(task_id), int(minutes)
    from datetime import timedelta
    from services import reminders as reminders_service
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