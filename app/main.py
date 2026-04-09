"""Application entry point.

Supports two modes:
- Webhook (production): set PUBLIC_BASE_URL in .env
- Polling (development):  leave PUBLIC_BASE_URL empty
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from app.config import settings
from app.database.models import Base
from app.database.session import AsyncSessionFactory, engine
from app.handlers import email_handler, payment, start, subscription, tariff
from app.middleware import DbSessionMiddleware
from app.scheduler import build_scheduler
from app.webhook.yookassa_webhook import handle_yookassa

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Register DB session middleware for both messages and callback queries
    dp.message.middleware(DbSessionMiddleware(AsyncSessionFactory))
    dp.callback_query.middleware(DbSessionMiddleware(AsyncSessionFactory))

    # Register routers (order matters for state-based routing)
    dp.include_router(start.router)
    dp.include_router(tariff.router)
    dp.include_router(email_handler.router)
    dp.include_router(payment.router)
    dp.include_router(subscription.router)

    return dp


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    dp: Dispatcher = app["dp"]

    # Create tables (idempotent — use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Set webhook
    if settings.PUBLIC_BASE_URL:
        webhook_url = f"{settings.PUBLIC_BASE_URL}/webhook/bot"
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
        log.info("Webhook set to %s", webhook_url)

    # Start scheduler
    scheduler = build_scheduler(bot, AsyncSessionFactory)
    scheduler.start()
    app["scheduler"] = scheduler
    log.info("Scheduler started")


async def on_shutdown(app: web.Application) -> None:
    bot: Bot = app["bot"]
    scheduler = app.get("scheduler")
    if scheduler:
        scheduler.shutdown(wait=False)

    if settings.PUBLIC_BASE_URL:
        await bot.delete_webhook()

    await bot.session.close()
    await engine.dispose()
    log.info("Shutdown complete")


def build_app(bot: Bot, dp: Dispatcher) -> web.Application:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app["session_factory"] = AsyncSessionFactory

    # Telegram updates
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(
        app, path="/webhook/bot"
    )
    setup_application(app, dp, bot=bot)

    # YooKassa notifications
    app.router.add_post("/webhook/yookassa", handle_yookassa)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    """Development mode: long polling."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler = build_scheduler(bot, AsyncSessionFactory)
    scheduler.start()

    log.info("Starting polling mode")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    if settings.PUBLIC_BASE_URL:
        app = build_app(bot, dp)
        log.info(
            "Starting webhook server on %s:%s", settings.WEBAPP_HOST, settings.WEBAPP_PORT
        )
        web.run_app(app, host=settings.WEBAPP_HOST, port=settings.WEBAPP_PORT)
    else:
        asyncio.run(run_polling(bot, dp))


if __name__ == "__main__":
    main()
