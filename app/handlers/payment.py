"""Payment confirmation and navigation handlers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.keyboards.keyboards import payment_link_kb, tariff_selection_kb
from app.repositories import event_logs, payments
from app.services import payment_service
from app.states.states import BotStates
from app.tariffs import get_tariff

log = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "payment:confirm", BotStates.preview)
async def on_pay(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    tg = callback.from_user
    data = await state.get_data()
    tariff_code = data.get("tariff_code", "teleport_1m")

    try:
        tariff = get_tariff(tariff_code)
    except KeyError:
        await callback.message.answer("❌ Тариф не найден. Начните сначала.")  # type: ignore[union-attr]
        await state.clear()
        return

    # Check for a reusable pending payment
    recent = await payments.get_recent_pending(
        session,
        tg_user_id=tg.id,
        tariff=tariff_code,
        minutes=settings.PAYMENT_REUSE_MINUTES,
    )

    if recent:
        await event_logs.log(
            session,
            "payment_reused",
            telegram_user_id=tg.id,
            payment_id=recent.payment_id,
            tariff=tariff_code,
        )
        confirmation_url = recent.confirmation_url
        log.info("Reusing pending payment %s for user %s", recent.payment_id, tg.id)
    else:
        # Create new YooKassa payment
        try:
            result = await payment_service.create_payment(
                tariff=tariff,
                tg_user_id=tg.id,
                return_url=settings.YOOKASSA_RETURN_URL,
            )
        except Exception:
            log.exception("Failed to create YooKassa payment for user %s", tg.id)
            await callback.message.answer(  # type: ignore[union-attr]
                "❌ Не удалось создать платёж. Попробуйте позже."
            )
            return

        payment_id: str = result["id"]
        confirmation_url: str = result.get("confirmation", {}).get("confirmation_url", "")

        await payments.create(
            session,
            payment_id=payment_id,
            tg_user_id=tg.id,
            username=tg.username,
            tariff=tariff_code,
            confirmation_url=confirmation_url,
        )
        await event_logs.log(
            session,
            "payment_created",
            telegram_user_id=tg.id,
            payment_id=payment_id,
            tariff=tariff_code,
        )

    await state.set_state(BotStates.main)
    await callback.message.answer(  # type: ignore[union-attr]
        "🔗 Перейдите по ссылке для оплаты:",
        reply_markup=payment_link_kb(confirmation_url, settings.ADMIN_USERNAME),
    )


@router.callback_query(F.data == "payment:back", BotStates.preview)
async def on_back(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BotStates.choosing_tariff)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "💳 Выберите тариф:",
        reply_markup=tariff_selection_kb(),
    )
