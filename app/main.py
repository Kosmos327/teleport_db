"""Application entry point.

FastAPI serves the YooKassa webhook while aiogram polling runs concurrently
as a background asyncio task (started inside FastAPI lifespan).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI

from app.config import settings
from app.database.models import Base
from app.database.session import AsyncSessionFactory, engine
from app.handlers import email_handler, payment, start, subscription, tariff
from app.middleware import DbSessionMiddleware
from app.scheduler import build_scheduler
from app.webhook.yookassa_webhook import router as yookassa_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(DbSessionMiddleware(AsyncSessionFactory))
dp.callback_query.middleware(DbSessionMiddleware(AsyncSessionFactory))
dp.include_router(start.router)
dp.include_router(tariff.router)
dp.include_router(email_handler.router)
dp.include_router(payment.router)
dp.include_router(subscription.router)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # Create tables (idempotent — use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start scheduler
    scheduler = build_scheduler(bot, AsyncSessionFactory)
    scheduler.start()
    log.info("Scheduler started")

    # Start aiogram polling in the background so it runs alongside FastAPI
    polling_task = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )
    log.info("Polling task created")

    # Store bot in app state so webhook handlers can access it without circular imports
    application.state.bot = bot
    application.state.session_factory = AsyncSessionFactory

    try:
        yield
    finally:
        # Stop polling
        polling_task.cancel()
        await asyncio.gather(polling_task, return_exceptions=True)
        log.info("Polling stopped")

        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()
        log.info("Shutdown complete")


app = FastAPI(lifespan=lifespan)
app.include_router(yookassa_router)
