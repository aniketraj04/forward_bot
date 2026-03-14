from aiogram.fsm.state import State, StatesGroup


class RuleState(StatesGroup):
    Waiting_source      = State()
    Waiting_destination = State()


class EditRuleState(StatesGroup):
    ChoosingAction       = State()
    AddingDestination    = State()
    RemovingDestination  = State()
    AddingBlacklist      = State()
    RemovingBlacklist    = State()


class DelayState(StatesGroup):
    WaitingDelay = State()