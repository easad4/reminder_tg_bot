from aiogram.fsm.state import State, StatesGroup


class CreateTask(StatesGroup):
    title = State()
    description = State()
    date = State()
    time_h = State()
    time_m = State()
    priority = State()
    remind = State()
    confirm = State()


class EditTask(StatesGroup):
    waiting_value = State()


class SettingsFSM(StatesGroup):
    timezone = State()
    digest = State()