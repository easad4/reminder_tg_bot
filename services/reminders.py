import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

import database as db
from services import tasks as tasks_service
from services import users as users_service

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")
_bot = None


def set_bot(bot) -> None:
    global _bot
    _bot = bot


def start() -> None:
    if not scheduler.running:
        scheduler.start()
        log.info("Scheduler started")


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def _job_id(rid: int) -> str:
    return f"rem_{rid}"


def schedule_reminder(reminder_id: int, fire_at_utc: datetime) -> None:
    jid = _job_id(reminder_id)
    try:
        scheduler.remove_job(jid)
    except Exception:
        pass
    if fire_at_utc.tzinfo is None:
        fire_at_utc = fire_at_utc.replace(tzinfo=timezone.utc)
    if fire_at_utc <= datetime.now(timezone.utc):
        # уже просрочено — отправим сразу
        fire_at_utc = datetime.now(timezone.utc) + timedelta(seconds=5)
    scheduler.add_job(
        fire_reminder,
        DateTrigger(run_date=fire_at_utc),
        args=[reminder_id],
        id=jid,
        replace_existing=True,
        misfire_grace_time=3600,
    )


async def fire_reminder(reminder_id: int) -> None:
    try:
        rem = await tasks_service.get_reminder(reminder_id)
        if rem is None or rem["sent"]:
            return
        task = await tasks_service.get_task(rem["task_id"], rem["user_id"])
        if task is None or task["status"] == "done":
            await tasks_service.mark_reminder_sent(reminder_id)
            return

        user = await users_service.get_user(rem["user_id"])
        tz_name = user["timezone"] if user else "Europe/Moscow"
        due_local = tasks_service._parse(task["due_utc"]).astimezone(ZoneInfo(tz_name))

        emoji = tasks_service.PRIORITY_EMOJI.get(task["priority"], "🟡")
        prio = tasks_service.PRIORITY_NAME.get(task["priority"], "средний")
        text = (
            "⏰ <b>НАПОМИНАНИЕ</b>\n\n"
            f"📌 <b>{task['title']}</b>\n"
            f"🗓 {due_local.strftime('%d.%m.%Y %H:%M')}\n"
            f"{emoji} Приоритет: {prio}"
        )
        if task["description"]:
            text += f"\n\n{task['description']}"

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"t:done:{task['id']}")],
            [
                InlineKeyboardButton(text="⏰ +5 минут", callback_data=f"t:post:{task['id']}:5"),
                InlineKeyboardButton(text="⏰ +15 минут", callback_data=f"t:post:{task['id']}:15"),
            ],
            [InlineKeyboardButton(text="📝 Открыть задачу", callback_data=f"t:view:{task['id']}")],
        ])
        try:
            await _bot.send_message(rem["user_id"], text, reply_markup=kb)
        except Exception as e:
            log.exception("Reminder send failed: %s", e)

        await tasks_service.mark_reminder_sent(reminder_id)
        log.info("Reminder %s sent for task %s", reminder_id, task["id"])
    except Exception:
        log.exception("fire_reminder failed for id=%s", reminder_id)


async def restore_all() -> None:
    rows = await tasks_service.get_pending_reminders()
    now = datetime.now(timezone.utc)
    for r in rows:
        fire_at = tasks_service._parse(r["fire_at_utc"])
        if fire_at <= now:
            # отправляем в течение нескольких секунд
            schedule_reminder(r["id"], now + timedelta(seconds=3))
        else:
            schedule_reminder(r["id"], fire_at)
    log.info("Restored %d pending reminders", len(rows))


# ---------- Daily digest ----------

def _digest_job_id(user_id: int) -> str:
    return f"digest_{user_id}"


def schedule_digest(user_id: int, tz_name: str, digest_time: str) -> None:
    jid = _digest_job_id(user_id)
    try:
        scheduler.remove_job(jid)
    except Exception:
        pass
    try:
        hh, mm = map(int, digest_time.split(":"))
        scheduler.add_job(
            send_digest,
            CronTrigger(hour=hh, minute=mm, timezone=ZoneInfo(tz_name)),
            args=[user_id],
            id=jid,
            replace_existing=True,
        )
    except Exception:
        log.exception("Cannot schedule digest for user %s", user_id)


async def send_digest(user_id: int) -> None:
    try:
        user = await users_service.get_user(user_id)
        if user is None:
            return
        tz_name = user["timezone"]
        rows, _ = await tasks_service.list_tasks(user_id, "today", tz_name, page=0, per_page=50)
        if not rows:
            return
        lines = ["☀️ <b>Сводка на сегодня</b>\n"]
        for r in rows:
            due_local = tasks_service._parse(r["due_utc"]).astimezone(ZoneInfo(tz_name))
            emoji = tasks_service.PRIORITY_EMOJI.get(r["priority"], "🟡")
            lines.append(f"{emoji} {due_local.strftime('%H:%M')} — {r['title']}")
        try:
            await _bot.send_message(user_id, "\n".join(lines))
        except Exception as e:
            log.warning("Digest send failed: %s", e)
    except Exception:
        log.exception("send_digest failed for %s", user_id)


async def restore_digests() -> None:
    for u in await users_service.all_users():
        schedule_digest(u["tg_id"], u["timezone"], u["digest_time"])