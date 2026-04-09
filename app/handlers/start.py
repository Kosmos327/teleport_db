"""Start & consent handlers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.keyboards import consent_kb, main_menu_kb
from app.repositories import event_logs, users
from app.states.states import BotStates

log = logging.getLogger(__name__)
router = Router()

CONSENT_TEXT = (
    "👋 Привет!\n\n"
    "Перед началом работы ознакомьтесь с условиями:\n"
    "• <a href='https://example.com/policy'>Политика конфиденциальности</a>\n"
    "• <a href='https://example.com/offer'>Публичная оферта</a>\n\n"
    "Нажмите <b>«Согласен»</b>, чтобы продолжить."
)

MAIN_MENU_TEXT = (
    "🏠 <b>Главное меню</b>\n\n"
    "Выберите действие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    tg = message.from_user
    if tg is None:
        return

    await users.get_or_create(
        session,
        tg_user_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
    )
    await event_logs.log(
        session,
        "user_started",
        telegram_user_id=tg.id,
        username=tg.username,
    )

    await state.set_state(BotStates.waiting_start)
    await message.answer(CONSENT_TEXT, reply_markup=consent_kb(), parse_mode="HTML")


@router.callback_query(F.data == "consent:agree", BotStates.waiting_start)
async def on_consent(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BotStates.main)
    await callback.message.edit_text(  # type: ignore[union-attr]
        MAIN_MENU_TEXT,
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:main")
async def go_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BotStates.main)
    await callback.message.edit_text(  # type: ignore[union-attr]
        MAIN_MENU_TEXT,
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
