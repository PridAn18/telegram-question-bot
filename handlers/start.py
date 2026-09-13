from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import keyboards
from utils.constants import START_TEXT

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db) -> None:
    user = message.from_user
    db.register_user(user.id, user.username, user.first_name)
    await message.answer(START_TEXT, reply_markup=keyboards.start_button())