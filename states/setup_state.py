from aiogram.fsm.state import State, StatesGroup

class SetupMama(StatesGroup):
    getting_mama_name = State()
    choosing_child = State()
    choosing_gender = State()