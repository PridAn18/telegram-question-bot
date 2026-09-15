import logging
import re
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

import keyboards
from services.question_service import QuestionService
from utils.constants import NO_QUESTIONS_TEXT, START_TEXT

logger = logging.getLogger(__name__)

router = Router()

last_question: dict[int, dict] = {}


def _question_text(question: dict) -> str:
    text = f"#{question['id']}\nВопрос:\n{escape(str(question['question']))}"
    if question["category"]:
        text += f"\n\nКатегория: {escape(str(question['category']))}"
    return text


def _format_answer(answer: str) -> str:
    answer = answer.strip()

    fence_match = re.fullmatch(r"```([a-zA-Z0-9_+-]*)\n([\s\S]*?)\n```", answer)
    if fence_match:
        lang = fence_match.group(1).strip()
        body = fence_match.group(2)
        body = escape(body)
        if lang:
            return f'<pre><code class="language-{escape(lang)}">{body}</code></pre>'
        return f"<pre>{body}</pre>"

    return escape(answer).replace("\n", "\n")


def clear_last_question(question_id: int) -> None:
    for user_id, question in list(last_question.items()):
        if question["id"] == question_id:
            last_question.pop(user_id, None)


@router.callback_query(F.data == "start_quiz")
async def start_quiz(callback: CallbackQuery, db) -> None:
    await callback.answer()
    service = QuestionService(db)
    question = service.get_next_question(callback.from_user.id)
    if question is None:
        await callback.message.answer(NO_QUESTIONS_TEXT)
        return
    last_question[callback.from_user.id] = question
    await callback.message.answer(_question_text(question))


@router.message(F.text)
async def on_answer(message: Message, db) -> None:
    if message.text.startswith("/"):
        return

    question = last_question.get(message.from_user.id)
    if question is None:
        await message.answer(START_TEXT, reply_markup=keyboards.start_button())
        return

    db.touch_user(message.from_user.id)
    await message.answer(
        f"Правильный ответ:\n{_format_answer(question['answer'])}",
        reply_markup=keyboards.next_button(),
    )


@router.callback_query(F.data == "next_question")
async def next_question(callback: CallbackQuery, db) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    question = last_question.pop(user_id, None)
    service = QuestionService(db)
    if question is not None:
        service.mark_answered(user_id, question["id"])

    row = service.get_next_question(user_id)
    if row is None:
        await callback.message.answer(
            NO_QUESTIONS_TEXT, reply_markup=keyboards.start_button()
        )
        return

    last_question[user_id] = row
    await callback.message.answer(_question_text(row))