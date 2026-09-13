import csv
import io
import logging
import os
import time

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile, FSInputFile, Message

import config
import keyboards
from handlers.questions import clear_last_question
from services.import_service import ImportService
from states import AddQuestion, DeleteQuestion, ImportQuestions, ResetDb
from utils.constants import VERSION

logger = logging.getLogger(__name__)

router = Router()

MAX_IMPORT_SIZE = 10 * 1024 * 1024


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        return event.from_user.id in config.ADMIN_IDS


def _memory_mb() -> float:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except (OSError, ValueError):
        pass
    return 0.0


def _format_uptime(seconds: float) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{days}д {hours}ч {minutes}м {sec}с"


def _tail(path: str, n: int = 300) -> str:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        read_size = min(size, 64 * 1024)
        f.seek(size - read_size)
        data = f.read()
    lines = data.splitlines()
    return "\n".join(line.decode("utf-8", errors="replace") for line in lines[-n:])


@router.message(Command("add"), IsAdmin())
async def cmd_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddQuestion.question)
    await message.answer("Введи вопрос:")


@router.message(AddQuestion.question, IsAdmin())
async def add_question(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправь вопрос текстом:")
        return
    await state.update_data(question=message.text.strip())
    await state.set_state(AddQuestion.answer)
    await message.answer("Введи ответ:")


@router.message(AddQuestion.answer, IsAdmin())
async def add_answer(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправь ответ текстом:")
        return
    await state.update_data(answer=message.text.strip())
    await state.set_state(AddQuestion.category)
    await message.answer("Введи категорию (создастся автоматически, если её нет):")


@router.message(AddQuestion.category, IsAdmin())
async def add_category(message: Message, state: FSMContext, db) -> None:
    if not message.text:
        await message.answer("Отправь название категории текстом:")
        return
    data = await state.get_data()
    category = message.text.strip()
    category_id = db.get_or_create_category(category)
    added = db.add_question(category_id, data["question"], data["answer"])
    await state.clear()
    if added:
        logger.info(
            "Добавлен вопрос «%s» в категорию «%s»", data["question"], category
        )
        await message.answer(
            "Вопрос сохранён.\n\n"
            f"Категория: {category}\n"
            f"Вопрос: {data['question']}\n"
            f"Ответ: {data['answer']}"
        )
    else:
        await message.answer("Такой вопрос уже есть в этой категории — пропущено.")


@router.message(Command("import"), IsAdmin())
async def cmd_import(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ImportQuestions.waiting_file)
    await message.answer(
        "Отправь CSV-файл с заголовком:\n\ncategory,question,answer"
    )


@router.message(ImportQuestions.waiting_file, F.document, IsAdmin())
async def import_file(message: Message, state: FSMContext, db) -> None:
    document = message.document
    if not document.file_name.lower().endswith(".csv"):
        await message.answer("Нужно отправить файл в формате CSV.")
        return
    if document.file_size > MAX_IMPORT_SIZE:
        await message.answer("Файл слишком большой, максимум 10 МБ.")
        return

    raw = await message.bot.download(document.file_id)
    stats = ImportService(db).import_bytes(raw.read())
    await state.clear()

    logger.info(
        "Импорт из %s: %s", document.file_name, stats
    )
    await message.answer(
        "Импорт завершён.\n"
        f"Добавлено категорий: {stats['categories_added']}\n"
        f"Добавлено вопросов: {stats['questions_added']}\n"
        f"Пропущено дублей: {stats['duplicates']}"
    )


@router.message(Command("export"), IsAdmin())
async def cmd_export(message: Message, db) -> None:
    rows = db.export_rows()
    if not rows:
        await message.answer("База пуста, экспортировать нечего.")
        return
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["category", "question", "answer"])
    writer.writerows(rows)
    data = buffer.getvalue().encode("utf-8-sig")
    logger.info("Экспорт: %d вопросов", len(rows))
    await message.answer_document(
        BufferedInputFile(data, filename="questions.csv")
    )


@router.message(Command("health"), IsAdmin())
async def cmd_health(message: Message, db, started_at) -> None:
    text = (
        "Статус: OK\n"
        f"Время работы: {_format_uptime(time.monotonic() - started_at)}\n"
        f"Вопросов: {db.count_questions()}\n"
        f"Категорий: {db.count_categories()}\n"
        f"Пользователей: {db.count_users()}\n"
        f"Размер базы: {round(db.db_size() / 1024 / 1024, 2)} МБ\n"
        f"Использование памяти: {_memory_mb()} МБ\n"
        f"Версия: {VERSION}"
    )
    await message.answer(text)


@router.message(Command("logs"), IsAdmin())
async def cmd_logs(message: Message) -> None:
    if not os.path.exists(config.LOG_PATH):
        await message.answer("Лог-файл пока отсутствует.")
        return
    content = _tail(config.LOG_PATH, 300)
    if len(content) > 3500:
        await message.answer_document(
            FSInputFile(config.LOG_PATH, filename="bot.log")
        )
        return
    await message.answer(f"Последние строки bot.log:\n\n{content}")


@router.message(Command("delete"), IsAdmin())
async def cmd_delete(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(DeleteQuestion.waiting_id)
    await message.answer("Введи ID вопроса для удаления.")


@router.message(DeleteQuestion.waiting_id, IsAdmin())
async def delete_ask_id(message: Message, state: FSMContext, db) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Нужно отправить число — ID вопроса.")
        return
    question_id = int(message.text.strip())
    question = db.get_question_by_id(question_id)
    if question is None:
        await message.answer(f"Вопрос с ID {question_id} не найден.")
        await state.clear()
        return
    await state.update_data(question_id=question_id)
    await state.set_state(DeleteQuestion.confirm)
    text = f"#{question['id']}\n{question['question']}"
    if question["category"]:
        text += f"\n\nКатегория: {question['category']}"
    await message.answer(
        f"Точно удалить этот вопрос?\n\n{text}",
        reply_markup=keyboards.confirm_delete_button(),
    )


@router.callback_query(F.data == "confirm_delete", IsAdmin())
async def confirm_delete(
    callback: CallbackQuery, state: FSMContext, db
) -> None:
    await callback.answer()
    data = await state.get_data()
    question_id = data.get("question_id")
    if question_id is None:
        await state.clear()
        await callback.message.answer(
            "Данные удаления не найдены. Используй /delete заново."
        )
        return
    db.delete_progress_for_question(question_id)
    db.delete_question_by_id(question_id)
    clear_last_question(question_id)
    await state.clear()
    logger.info(
        "Вопрос #%s удалён администратором %s",
        question_id,
        callback.from_user.id,
    )
    await callback.message.answer(
        f"Вопрос #{question_id} удалён вместе с прогрессом пользователей."
    )


@router.callback_query(F.data == "cancel_delete", IsAdmin())
async def cancel_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer("Удаление отменено.")


@router.message(Command("resetdb"), IsAdmin())
async def cmd_resetdb(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ResetDb.confirm)
    await state.update_data(confirm_steps=0)
    await message.answer(
        "⚠️ Внимание! Это удалит ВСЕ вопросы, категории и прогресс "
        "пользователей без возможности восстановления.\n\n"
        "Продолжить?",
        reply_markup=keyboards.confirm_reset_db_button(),
    )


@router.callback_query(F.data == "confirm_reset_db", IsAdmin())
async def confirm_reset_db(
    callback: CallbackQuery, state: FSMContext, db
) -> None:
    await callback.answer()
    data = await state.get_data()
    steps = data.get("confirm_steps", 0)
    if steps == 0:
        await state.update_data(confirm_steps=1)
        await callback.message.answer(
            "Последнее подтверждение: сброс необратим, все данные будут "
            "удалены навсегда.\n\n"
            "Нажми «Подтвердить» ещё раз.",
            reply_markup=keyboards.confirm_reset_db_button(),
        )
        return
    db.drop_and_recreate_db()
    await state.clear()
    logger.warning(
        "База данных полностью сброшена администратором %s",
        callback.from_user.id,
    )
    await callback.message.answer("База данных сброшена. Все данные удалены.")


@router.callback_query(F.data == "cancel_reset_db", IsAdmin())
async def cancel_reset_db(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer("Сброс отменён.")