"""aiohttp handler for YooKassa payment webhook notifications."""

from __future__ import annotations

import logging
from datetime import timezone

from aiohttp import web
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.keyboards.keyboards import admin_contact_kb
from app.repositories import event_logs, invite_links, payment_methods, payments, subscriptions, users
from app.services import invite_service, payment_service
from app.tariffs import get_tariff
from app.utils.dt import add_months_keep_day, now_local

log = logging.getLogger(__name__)


async def handle_yookassa(request: web.Request) -> web.Response:
    """Entry point for YooKassa webhook POST requests."""
    try:
        body = await request.json()
    except Exception:
        log.warning("YooKassa webhook: invalid JSON body")
        return web.Response(status=400)

    event_type: str = body.get("event", "")
    obj: dict = body.get("object", {})
    payment_id: str = obj.get("id", "")

    log.info("YooKassa webhook: event=%s payment_id=%s", event_type, payment_id)

    if not payment_id:
        return web.Response(status=400)

    session_factory: async_sessionmaker[AsyncSession] = request.app["session_factory"]
    bot: Bot = request.app["bot"]

    # Verify the payment with YooKassa (do not trust payload blindly)
    try:
        yk_payment = await payment_service.fetch_payment(payment_id)
    except Exception:
        log.exception("Failed to fetch payment %s from YooKassa", payment_id)
        return web.Response(status=500)

    yk_status: str = yk_payment.get("status", "")

    async with session_factory() as session:
        async with session.begin():
            await event_logs.log(
                session,
                "webhook_received",
                payload={"event": event_type, "payment_id": payment_id, "status": yk_status},
            )

            if event_type == "payment.succeeded" and yk_status == "succeeded":
                await _handle_succeeded(session, bot, yk_payment)
            elif event_type == "payment.canceled" and yk_status == "canceled":
                await _handle_canceled(session, yk_payment)

    return web.Response(status=200)


async def _handle_succeeded(
    session: AsyncSession, bot: Bot, yk_payment: dict
) -> None:
    payment_id: str = yk_payment["id"]
    metadata: dict = yk_payment.get("metadata", {})
    tg_user_id: int = int(metadata.get("tg_user_id", 0))
    tariff_code: str = metadata.get("tariff", "teleport_1m")
    is_renew: bool = metadata.get("is_renew", "false").lower() == "true"

    if not tg_user_id:
        log.error("payment.succeeded: missing tg_user_id in metadata for %s", payment_id)
        return

    now = now_local()

    # Update payment record
    try:
        tariff = get_tariff(tariff_code)
    except KeyError:
        log.error("Unknown tariff %s in payment %s", tariff_code, payment_id)
        return

    expires_at = add_months_keep_day(now, tariff["duration_months"])

    await payments.update_status(
        session,
        payment_id=payment_id,
        status="succeeded",
        paid_at=now,
        expires_at=expires_at,
    )

    # Handle saved payment method
    yk_pm: dict = yk_payment.get("payment_method", {})
    pm_saved: bool = yk_pm.get("saved", False)
    pm_id: str | None = yk_pm.get("id") if pm_saved else None

    if pm_id:
        user = await users.get(session, tg_user_id)
        next_charge = add_months_keep_day(now, tariff["duration_months"])
        await payment_methods.upsert(
            session,
            tg_user_id=tg_user_id,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            payment_method_id=pm_id,
            last_payment_id=payment_id,
            next_charge_at=next_charge,
        )
        await event_logs.log(
            session, "card_linked", telegram_user_id=tg_user_id, pm_id=pm_id
        )

    # Create or extend subscription
    await subscriptions.create(
        session,
        telegram_user_id=tg_user_id,
        tariff_code=tariff_code,
        starts_at=now,
        expires_at=expires_at,
        source_payment_id=payment_id,
        auto_renew_enabled=bool(pm_id),
    )

    await event_logs.log(
        session,
        "payment_succeeded",
        telegram_user_id=tg_user_id,
        payment_id=payment_id,
        tariff=tariff_code,
        is_renew=is_renew,
    )

    # Send invite link
    try:
        link_obj = await invite_service.create_invite_link(bot)
        await invite_links.create(
            session,
            telegram_user_id=tg_user_id,
            chat_id=settings.ACCESS_CHAT_ID,
            invite_link=link_obj.invite_link,
            expires_at=link_obj.expire_date,
        )
        await event_logs.log(
            session,
            "invite_sent",
            telegram_user_id=tg_user_id,
            invite_link=link_obj.invite_link,
        )

        confirmation_text = (
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"Тариф: <b>{tariff['name']}</b>\n"
            f"Доступ до: <b>{expires_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"🔗 Ваша персональная ссылка для вступления:\n{link_obj.invite_link}\n\n"
            f"⚠️ Ссылка одноразовая и действительна 24 часа."
        )
        await bot.send_message(tg_user_id, confirmation_text, parse_mode="HTML")
    except Exception:
        log.exception("Failed to create/send invite link for user %s", tg_user_id)
        await event_logs.log(
            session, "invite_failed", telegram_user_id=tg_user_id, payment_id=payment_id
        )
        fallback_text = metadata.get("tg_user_id", str(tg_user_id))
        prefill = f"Мне не пришла ссылка после оплаты. ID платежа: {payment_id}"
        await bot.send_message(
            tg_user_id,
            (
                "✅ Оплата принята!\n\n"
                "⚠️ Не удалось отправить ссылку-приглашение автоматически.\n"
                "Пожалуйста, свяжитесь с администратором:"
            ),
            reply_markup=admin_contact_kb(settings.ADMIN_USERNAME, prefill),
        )


async def _handle_canceled(session: AsyncSession, yk_payment: dict) -> None:
    payment_id: str = yk_payment["id"]
    metadata: dict = yk_payment.get("metadata", {})
    tg_user_id_str: str = metadata.get("tg_user_id", "")

    await payments.update_status(session, payment_id=payment_id, status="canceled")
    await event_logs.log(
        session,
        "payment_canceled",
        telegram_user_id=int(tg_user_id_str) if tg_user_id_str else None,
        payment_id=payment_id,
    )
    log.info("Payment %s canceled", payment_id)
