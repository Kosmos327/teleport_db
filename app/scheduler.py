"""APScheduler jobs: subscription reminders and auto-renewal."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.keyboards.keyboards import renew_reminder_kb
from app.repositories import event_logs, payment_methods, payments, subscriptions
from app.services import payment_service
from app.tariffs import get_tariff
from app.utils.dt import add_months_keep_day, fmt_dt, now_local

log = logging.getLogger(__name__)


async def send_prenotice_reminders(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Send renewal reminders for subscriptions expiring within PRENOTICE_DAYS."""
    async with session_factory() as session:
        async with session.begin():
            expiring = await subscriptions.list_expiring_soon(
                session, days=settings.PRENOTICE_DAYS
            )
            for sub in expiring:
                try:
                    await bot.send_message(
                        sub.telegram_user_id,
                        (
                            f"⏳ <b>Ваша подписка заканчивается!</b>\n\n"
                            f"До: <b>{fmt_dt(sub.expires_at)}</b>\n\n"
                            f"Нажмите кнопку ниже, чтобы продлить доступ."
                        ),
                        reply_markup=renew_reminder_kb(),
                        parse_mode="HTML",
                    )
                    await event_logs.log(
                        session,
                        "subscription_prenotice_sent",
                        telegram_user_id=sub.telegram_user_id,
                        sub_id=sub.id,
                        expires_at=sub.expires_at.isoformat(),
                    )
                except Exception:
                    log.exception(
                        "Failed to send prenotice to user %s", sub.telegram_user_id
                    )


async def run_autopay(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Attempt auto-renewal for subscriptions whose next_charge_at has passed."""
    async with session_factory() as session:
        async with session.begin():
            due = await payment_methods.list_due_for_charge(session)

    for pm in due:
        await _attempt_single_autopay(bot, session_factory, pm)


async def _attempt_single_autopay(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    pm_record,
) -> None:
    tg_user_id: int = pm_record.tg_user_id

    async with session_factory() as session:
        async with session.begin():
            # Check auto_renew is still enabled on the subscription
            sub = await subscriptions.get_active(session, tg_user_id)
            if sub and not sub.auto_renew_enabled:
                log.info(
                    "Skipping autopay for user %s: auto_renew disabled", tg_user_id
                )
                return

            try:
                tariff = get_tariff(pm_record.last_payment_id and "teleport_1m" or "teleport_1m")
            except KeyError:
                tariff = get_tariff("teleport_1m")

            await event_logs.log(
                session,
                "autopay_attempt",
                telegram_user_id=tg_user_id,
                pm_id=pm_record.payment_method_id,
                tariff=tariff["code"],
            )

        try:
            result = await payment_service.create_payment(
                tariff=tariff,
                tg_user_id=tg_user_id,
                is_renew=True,
                payment_method_id=pm_record.payment_method_id,
            )
        except Exception:
            log.exception("Autopay failed for user %s", tg_user_id)
            async with session_factory() as session:
                async with session.begin():
                    pm = await payment_methods.get_by_method_id(
                        session, pm_record.payment_method_id
                    )
                    if pm:
                        await payment_methods.record_autopay_attempt(
                            session, pm, payment_id="", status="failed"
                        )
                    await event_logs.log(
                        session,
                        "autopay_failed",
                        telegram_user_id=tg_user_id,
                        pm_id=pm_record.payment_method_id,
                    )
            return

        new_payment_id: str = result["id"]
        new_status: str = result.get("status", "pending")

        async with session_factory() as session:
            async with session.begin():
                now = now_local()
                expires_at = add_months_keep_day(now, tariff["duration_months"])
                await payments.create(
                    session,
                    payment_id=new_payment_id,
                    tg_user_id=tg_user_id,
                    username=pm_record.username,
                    tariff=tariff["code"],
                    confirmation_url="",
                    is_renew=True,
                )
                pm = await payment_methods.get_by_method_id(
                    session, pm_record.payment_method_id
                )
                if pm:
                    await payment_methods.record_autopay_attempt(
                        session, pm, payment_id=new_payment_id, status=new_status
                    )
                    if new_status == "succeeded":
                        pm.next_charge_at = add_months_keep_day(
                            now, tariff["duration_months"]
                        )

                if new_status == "succeeded":
                    await subscriptions.create(
                        session,
                        telegram_user_id=tg_user_id,
                        tariff_code=tariff["code"],
                        starts_at=now,
                        expires_at=expires_at,
                        source_payment_id=new_payment_id,
                        auto_renew_enabled=True,
                    )
                    await event_logs.log(
                        session,
                        "autopay_succeeded",
                        telegram_user_id=tg_user_id,
                        payment_id=new_payment_id,
                    )
                    try:
                        await bot.send_message(
                            tg_user_id,
                            (
                                f"✅ <b>Подписка автоматически продлена!</b>\n\n"
                                f"Тариф: <b>{tariff['name']}</b>\n"
                                f"До: <b>{fmt_dt(expires_at)}</b>"
                            ),
                            parse_mode="HTML",
                        )
                    except Exception:
                        log.warning(
                            "Could not notify user %s about autopay success", tg_user_id
                        )
                else:
                    await event_logs.log(
                        session,
                        "autopay_failed",
                        telegram_user_id=tg_user_id,
                        payment_id=new_payment_id,
                        status=new_status,
                    )


def build_scheduler(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Daily prenotice at 09:00 local time
    scheduler.add_job(
        send_prenotice_reminders,
        trigger="cron",
        hour=9,
        minute=0,
        kwargs={"bot": bot, "session_factory": session_factory},
        id="prenotice",
        replace_existing=True,
    )

    # Autopay check every hour
    scheduler.add_job(
        run_autopay,
        trigger="interval",
        hours=1,
        kwargs={"bot": bot, "session_factory": session_factory},
        id="autopay",
        replace_existing=True,
    )

    return scheduler
