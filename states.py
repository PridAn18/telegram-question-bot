from aiogram.fsm.state import State, StatesGroup


class AddQuestion(StatesGroup):
    question = State()
    answer = State()
    category = State()


class ImportQuestions(StatesGroup):
    waiting_file = State()