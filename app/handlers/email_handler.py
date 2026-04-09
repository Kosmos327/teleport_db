"""Email collection handler."""

from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.keyboards.keyboards import payment_preview_kb
from app.repositories import event_logs, users
from app.states.states import BotStates
from app.tariffs import get_tariff

log = logging.getLogger(__name__)
router = Router()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.message(BotStates.waiting_email)
async def receive_email(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    raw = (message.text or "").strip()
    if not _EMAIL_RE.match(raw):
        await message.answer(
            "❌ Неверный формат e-mail. Пожалуйста, введите корректный адрес:"
        )
        return

    tg = message.from_user
    email = raw.lower()

    await users.set_email(session, tg.id, email)
    await event_logs.log(
        session,
        "email_saved",
        telegram_user_id=tg.id,
        email=email,
    )

    data = await state.get_data()
    tariff_code = data.get("tariff_code", "teleport_1m")
    tariff = get_tariff(tariff_code)

    await state.update_data(email=email)
    await state.set_state(BotStates.preview)

    text = (
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"Тариф: <b>{tariff['name']}</b>\n"
        f"Стоимость: <b>{tariff['price']} ₽</b>\n"
        f"Email для чека: <code>{email}</code>\n\n"
        f"Нажмите <b>«Оплатить»</b> для создания платежа."
    )
    await message.answer(
        text,
        reply_markup=payment_preview_kb(settings.ADMIN_USERNAME),
        parse_mode="HTML",
    )
