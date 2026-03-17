from aiogram.fsm.state import StatesGroup, State

class Chatting(StatesGroup):
    in_dialogue = State()
    waiting_for_response = State()
    collecting_files = State()
