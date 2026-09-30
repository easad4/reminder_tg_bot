from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards.main import main_menu
from services import users as users_service
from services import reminders as reminders_service

router = Router()

HELP = (
    "🤖 <b>Бот-планировщик</b>\n\n"
    "Управление — только кнопками снизу.\n\n"
    "📋 Мои задачи — активные задачи\n"
    "➕ Создать задачу — пошаговый мастер\n"
    "📅 Сегодня — задачи на сегодня\n"
    "⏳ Просроченные — невыполненные с истёкшим сроком\n"
    "✅ Выполненные — история\n"
    "⚙️ Настройки — часовой пояс и время сводки"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await users_service.ensure_user(message.from_user.id)
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n" + HELP,
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP, reply_markup=main_menu())