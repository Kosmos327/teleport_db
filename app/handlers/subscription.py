"""Subscription status handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.keyboards import subscription_status_kb
from app.repositories import event_logs, payment_methods, subscriptions
from app.utils.dt import fmt_dt

log = logging.getLogger(__name__)
router = Router()


async def _render_subscription_message(
    session: AsyncSession,
    tg_user_id: int,
) -> tuple[str, object]:
    """Build subscription status text and keyboard."""
    sub = await subscriptions.get_latest(session, tg_user_id)
    pm = await payment_methods.get_active(session, tg_user_id)

    if sub is None:
        text = (
            "📋 <b>Статус подписки</b>\n\n"
            "У вас нет активной подписки.\n"
            "Нажмите <b>«Телепорт (Оплатить)»</b>, чтобы подключить."
        )
        kb = subscription_status_kb(has_card=pm is not None, auto_renew=False)
    else:
        is_active = (
            sub.status == "active"
            and sub.expires_at > datetime.now(tz=timezone.utc)
        )

        status_icon = "✅" if is_active else "❌"
        auto_renew_text = "включено ✅" if sub.auto_renew_enabled else "отключено ❌"

        text = (
            f"📋 <b>Статус подписки</b>\n\n"
            f"Тариф: <b>{sub.tariff_code}</b>\n"
            f"Статус: {status_icon} {'активна' if is_active else 'истекла'}\n"
            f"До: <b>{fmt_dt(sub.expires_at)}</b>\n"
            f"Автопродление: {auto_renew_text}"
        )
        kb = subscription_status_kb(
            has_card=pm is not None,
            auto_renew=sub.auto_renew_enabled,
            sub_id=sub.id,
        )

    return text, kb


@router.callback_query(F.data == "menu:subscription")
async def show_subscription(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    tg = callback.from_user
    text, kb = await _render_subscription_message(session, tg.id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sub:refresh")
async def refresh_subscription(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer("Обновлено")
    tg = callback.from_user
    text, kb = await _render_subscription_message(session, tg.id)
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception:
        pass  # message unchanged — not an error


@router.callback_query(F.data == "sub:unlink_card")
async def unlink_card(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    tg = callback.from_user
    removed = await payment_methods.deactivate(session, tg.id)
    await event_logs.log(session, "card_unlinked", telegram_user_id=tg.id)
    if removed:
        await callback.answer("Карта отвязана.", show_alert=True)
    else:
        await callback.answer("Нет привязанной карты.", show_alert=True)

    text, kb = await _render_subscription_message(session, tg.id)
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("sub:toggle_renew:"))
async def toggle_auto_renew(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    _, _, sub_id_str, current_str = callback.data.split(":")  # type: ignore[union-attr]
    sub_id = int(sub_id_str)
    current = bool(int(current_str))
    new_value = not current

    await subscriptions.set_auto_renew(session, sub_id, new_value)
    await event_logs.log(
        session,
        "card_linked" if new_value else "card_unlinked",
        telegram_user_id=callback.from_user.id,
        sub_id=sub_id,
        auto_renew=new_value,
    )
    await callback.answer(
        "Автопродление включено ✅" if new_value else "Автопродление отключено ❌",
        show_alert=True,
    )

    text, kb = await _render_subscription_message(session, callback.from_user.id)
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception:
        pass
