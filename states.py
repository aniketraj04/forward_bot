from aiogram.fsm.state import StatesGroup, State

class RuleFSM(StatesGroup):
    source = State()
    destination = State()
    dest_count = State()
    dest_channels = State()