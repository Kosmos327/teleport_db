"""FSM states."""

from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    waiting_start = State()   # Showing consent / waiting for "Согласен"
    main = State()            # Main menu
    choosing_tariff = State() # Tariff selection
    waiting_email = State()   # Waiting for the user to enter their email
    preview = State()         # Payment preview / confirmation
