from aiogram.fsm.state import State, StatesGroup

class SetupMama(StatesGroup):
    getting_mama_name = State()
    getting_timezone = State()
    choosing_child = State()
    getting_child_name = State()
    getting_child_gender = State()
    getting_personality = State()