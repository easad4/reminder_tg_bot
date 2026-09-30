from zoneinfo import ZoneInfo
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.main import main_menu, task_actions_kb
from services import tasks as tasks_service
from services import users as users_service

router = Router()
PER_PAGE = 5


def _card(row, tz_name: str) -> str:
    from services.tasks import PRIORITY_EMOJI, PRIORITY_NAME, _parse
    due_local = _parse(row["due_utc"]).astimezone(ZoneInfo(tz_name))
    emoji = PRIORITY_EMOJI.get(row["priority"], "🟡")
    prio = PRIORITY_NAME.get(row["priority"], "средний")
    title = "✅ " if row["status"] == "done" else ""
    text = f"{title}📌 <b>{row['title']}</b>\n🗓 {due_local.strftime('%d.%m.%Y %H:%M')}\n{emoji} {prio}"
    if row["description"]:
        text += f"\n📝 {row['description']}"
    return text


async def _render_page(user_id: int, kind: str, page: int, tz_name: str):
    rows, total = await tasks_service.list_tasks(user_id, kind, tz_name, page, PER_PAGE)
    titles = {"my": "📋 Мои задачи", "today": "📅 Сегодня",
              "overdue": "⏳ Просроченные", "done": "✅ Выполненные"}
    header = f"<b>{titles[kind]}</b>  (стр. {page+1}/{(total-1)//PER_PAGE + 1 if total else 1})\n\n"
    if not rows:
        return header + "Пусто.", None

    text = header
    kb_rows = []
    for i, r in enumerate(rows, start=1):
        due = tasks_service._parse(r["due_utc"]).astimezone(ZoneInfo(tz_name))
        emoji = tasks_service.PRIORITY_EMOJI.get(r["priority"], "🟡")
        line = f"{i}. {emoji} {due.strftime('%d.%m %H:%M')} — {r['title']}"
        kb_rows.append([InlineKeyboardButton(text=line[:60], callback_data=f"t:view:{r['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"list:{kind}:{page-1}"))
    if (page + 1) * PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"list:{kind}:{page+1}"))
    if nav:
        kb_rows.append(nav)
    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(F.text == "📋 Мои задачи")
async def my_tasks(message: Message):
    await _send(message.from_user.id, "my", 0, message)


@router.message(F.text == "📅 Сегодня")
async def today_tasks(message: Message):
    await _send(message.from_user.id, "today", 0, message)


@router.message(F.text == "⏳ Просроченные")
async def overdue_tasks(message: Message):
    await _send(message.from_user.id, "overdue", 0, message)


@router.message(F.text == "✅ Выполненные")
async def done_tasks(message: Message):
    await _send(message.from_user.id, "done", 0, message)


async def _send(user_id: int, kind: str, page: int, message: Message):
    user = await users_service.get_user(user_id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    text, kb = await _render_page(user_id, kind, page, tz_name)
    if kb is None:
        await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("list:"))
async def page_cb(cb: CallbackQuery):
    _, kind, page = cb.data.split(":")
    user = await users_service.get_user(cb.from_user.id)
    tz_name = user["timezone"] if user else "Europe/Moscow"
    text, kb = await _render_page(cb.from_user.id, kind, int(page), tz_name)
    if kb is None:
        await cb.message.edit_text(text)
    else:
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()