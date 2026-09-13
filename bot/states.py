from aiogram.fsm.state import State, StatesGroup


class GarminConnectStates(StatesGroup):
    email = State()
    password = State()
    mfa = State()


class GoalCreateStates(StatesGroup):
    distance = State()
    time_choice = State()
    time_input = State()
    race_date = State()
