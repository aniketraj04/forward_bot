from aiogram.fsm.state import State, StatesGroup

class RuleState(StatesGroup):
    Waiting_source = State()
    Waiting_destination = State()

