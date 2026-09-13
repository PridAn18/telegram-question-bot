import csv
import io
import logging
import os
import time

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, FSInputFile, Message

import config
from services.import_service import ImportService
from states import AddQuestion, ImportQuestions
from utils.constants import VERSION

logger = logging.getLogger(__name__)

router = Router()

MAX_IMPORT_SIZE = 10 * 1024 * 1024


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in config.ADMIN_IDS


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