import logging
from datetime import datetime, timezone, timedelta
import database as db

log = logging.getLogger(__name__)

PRIORITY_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴"}
PRIORITY_NAME = {"low": "низкий", "medium": "средний", "high": "высокий"}


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def create_task(
    user_id: int,
    title: str,
    description: str | None,
    due_utc: datetime,
    priority: str,
    remind_before: int,
    repeat_rule: str | None = None,
) -> tuple[int, int, datetime]:
    conn = db.db()
    cur = await conn.execute(
        """INSERT INTO tasks
           (user_id, title, description, due_utc, priority, remind_before, repeat_rule)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, title, description, _iso(due_utc), priority, remind_before, repeat_rule),
    )
    task_id = cur.lastrowid
    await cur.close()

    fire_at = due_utc - timedelta(minutes=remind_before)
    cur = await conn.execute(
        "INSERT INTO reminders (task_id, user_id, fire_at_utc) VALUES (?,?,?)",
        (task_id, user_id, _iso(fire_at)),
    )
    reminder_id = cur.lastrowid
    await cur.close()
    await conn.commit()
    return task_id, reminder_id, fire_at.astimezone(timezone.utc)


async def get_task(task_id: int, user_id: int):
    cur = await db.db().execute(
        "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
    )
    row = await cur.fetchone()
    await cur.close()
    return row


async def list_tasks(user_id: int, kind: str, tz_name: str, page: int = 0, per_page: int = 5):
    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc)
    tz = ZoneInfo(tz_name)

    if kind == "my":
        where = "user_id=? AND status='active'"
        params = (user_id,)
        order = "due_utc ASC"
    elif kind == "today":
        local_now = now_utc.astimezone(tz)
        start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        where = "user_id=? AND status='active' AND due_utc>=? AND due_utc<?"
        params = (user_id, _iso(start_local), _iso(end_local))
        order = "due_utc ASC"
    elif kind == "overdue":
        where = "user_id=? AND status='active' AND due_utc<?"
        params = (user_id, _iso(now_utc))
        order = "due_utc ASC"
    elif kind == "done":
        where = "user_id=? AND status='done'"
        params = (user_id,)
        order = "completed_at DESC"
    else:
        raise ValueError(kind)

    conn = db.db()
    cur = await conn.execute(f"SELECT COUNT(*) AS c FROM tasks WHERE {where}", params)
    total = (await cur.fetchone())["c"]
    await cur.close()

    cur = await conn.execute(
        f"SELECT * FROM tasks WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        (*params, per_page, page * per_page),
    )
    rows = await cur.fetchall()
    await cur.close()
    return rows, total


async def mark_done(task_id: int, user_id: int) -> bool:
    conn = db.db()
    cur = await conn.execute(
        "UPDATE tasks SET status='done', completed_at=? WHERE id=? AND user_id=? AND status='active'",
        (datetime.now(timezone.utc).isoformat(), task_id, user_id),
    )
    changed = cur.rowcount
    await cur.close()
    await conn.execute(
        "UPDATE reminders SET sent=1 WHERE task_id=? AND sent=0", (task_id,)
    )
    await conn.commit()
    return changed > 0


async def delete_task(task_id: int, user_id: int) -> bool:
    conn = db.db()
    cur = await conn.execute(
        "DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
    )
    changed = cur.rowcount
    await cur.close()
    await conn.execute("DELETE FROM reminders WHERE task_id=?", (task_id,))
    await conn.commit()
    return changed > 0


async def update_task(task_id: int, user_id: int, **fields) -> bool:
    if not fields:
        return False
    allowed = {"title", "description", "due_utc", "priority", "remind_before", "repeat_rule"}
    keys = [k for k in fields if k in allowed]
    if not keys:
        return False
    values = []
    for k in keys:
        v = fields[k]
        if k == "due_utc" and isinstance(v, datetime):
            v = _iso(v)
        values.append(v)
    values.extend([task_id, user_id])
    conn = db.db()
    cur = await conn.execute(
        f"UPDATE tasks SET {', '.join(f'{k}=?' for k in keys)} WHERE id=? AND user_id=?",
        values,
    )
    changed = cur.rowcount
    await cur.close()
    await conn.commit()
    return changed > 0


async def reschedule_reminder(task_id: int, user_id: int, due_utc: datetime, remind_before: int):
    """Удаляет несданные напоминания задачи и создаёт одно новое.
    Возвращает (reminder_id, fire_at_utc)."""
    conn = db.db()
    await conn.execute(
        "DELETE FROM reminders WHERE task_id=? AND sent=0", (task_id,)
    )
    fire_at = due_utc - timedelta(minutes=remind_before)
    cur = await conn.execute(
        "INSERT INTO reminders (task_id, user_id, fire_at_utc) VALUES (?,?,?)",
        (task_id, user_id, _iso(fire_at)),
    )
    rid = cur.lastrowid
    await cur.close()
    await conn.commit()
    return rid, fire_at.astimezone(timezone.utc)


async def get_pending_reminders():
    cur = await db.db().execute(
        "SELECT * FROM reminders WHERE sent=0 ORDER BY fire_at_utc ASC"
    )
    rows = await cur.fetchall()
    await cur.close()
    return rows


async def get_reminder(reminder_id: int):
    cur = await db.db().execute("SELECT * FROM reminders WHERE id=?", (reminder_id,))
    row = await cur.fetchone()
    await cur.close()
    return row


async def mark_reminder_sent(reminder_id: int):
    conn = db.db()
    await conn.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
    await conn.commit()


async def create_next_repeat(task_row) -> None:
    """Создаёт следующую задачу для повторяющейся."""
    rule = task_row["repeat_rule"]
    if not rule:
        return
    due = _parse(task_row["due_utc"])
    if rule == "daily":
        nxt = due + timedelta(days=1)
    elif rule == "weekly":
        nxt = due + timedelta(weeks=1)
    elif rule == "monthly":
        nxt = due + timedelta(days=30)
    else:
        return
    await create_task(
        user_id=task_row["user_id"],
        title=task_row["title"],
        description=task_row["description"],
        due_utc=nxt,
        priority=task_row["priority"],
        remind_before=task_row["remind_before"],
        repeat_rule=rule,
    )