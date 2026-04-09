"""Tariff selection handlers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.keyboards import tariff_selection_kb
from app.repositories import event_logs, users
from app.states.states import BotStates
from app.tariffs import TARIFFS, get_tariff

log = logging.getLogger(__name__)
router = Router()

CHOOSE_TARIFF_TEXT = "💳 Выберите тариф:"


@router.callback_query(F.data == "menu:pay")
async def show_tariffs(callback: CallbackQuery, state: FSMContext) -> None:
    """Entry point: main menu → tariff selection (also used by '🔥 Продлить')."""
    await callback.answer()
    await state.set_state(BotStates.choosing_tariff)
    await callback.message.edit_text(  # type: ignore[union-attr]
        CHOOSE_TARIFF_TEXT,
        reply_markup=tariff_selection_kb(),
    )


@router.callback_query(F.data.startswith("tariff:"), BotStates.choosing_tariff)
async def tariff_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    tariff_code = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    try:
        tariff = get_tariff(tariff_code)
    except KeyError:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    tg = callback.from_user
    await event_logs.log(
        session,
        "tariff_selected",
        telegram_user_id=tg.id,
        tariff=tariff_code,
    )

    # Store chosen tariff in FSM
    await state.update_data(tariff_code=tariff_code)

    # Show product description
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        tariff["description"],
        parse_mode="HTML",
    )

    # Check if user already has a saved email
    email = await users.get_email(session, tg.id)
    if email:
        await state.update_data(email=email)
        await _show_preview(callback, state, tariff, email)
    else:
        await state.set_state(BotStates.waiting_email)
        await callback.message.answer(  # type: ignore[union-attr]
            "📧 Укажите ваш e-mail для получения чека:"
        )


async def _show_preview(
    callback: CallbackQuery,
    state: FSMContext,
    tariff: dict,
    email: str,
) -> None:
    from app.config import settings
    from app.keyboards.keyboards import payment_preview_kb

    await state.set_state(BotStates.preview)
    text = (
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"Тариф: <b>{tariff['name']}</b>\n"
        f"Стоимость: <b>{tariff['price']} ₽</b>\n"
        f"Email для чека: <code>{email}</code>\n\n"
        f"Нажмите <b>«Оплатить»</b> для создания платежа."
    )
    await callback.message.answer(  # type: ignore[union-attr]
        text,
        reply_markup=payment_preview_kb(settings.ADMIN_USERNAME),
        parse_mode="HTML",
    )
