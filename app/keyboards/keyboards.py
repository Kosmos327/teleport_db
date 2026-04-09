"""All keyboards used across the bot."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.tariffs import TARIFFS


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Телепорт (Оплатить)", callback_data="menu:pay")
    builder.button(text="📋 Подписка (Статус)", callback_data="menu:subscription")
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

def consent_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Согласен", callback_data="consent:agree")
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Tariff selection
# ---------------------------------------------------------------------------

def tariff_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, tariff in TARIFFS.items():
        label = f"{tariff['name']} / {tariff['price']} руб."
        builder.button(text=label, callback_data=f"tariff:{code}")
    builder.button(text="⬅️ Главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Payment preview
# ---------------------------------------------------------------------------

def payment_preview_kb(admin_username: str) -> InlineKeyboardMarkup:
    support_url = f"https://t.me/{admin_username}"
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", callback_data="payment:confirm")
    builder.button(text="⬅️ Назад", callback_data="payment:back")
    builder.button(text="💬 Задать вопрос", url=support_url)
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Payment link
# ---------------------------------------------------------------------------

def payment_link_kb(url: str, admin_username: str) -> InlineKeyboardMarkup:
    support_url = f"https://t.me/{admin_username}"
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Перейти к оплате", url=url)
    builder.button(text="💬 Задать вопрос", url=support_url)
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Admin contact (fallback when invite link fails)
# ---------------------------------------------------------------------------

def admin_contact_kb(admin_username: str, prefill_text: str) -> InlineKeyboardMarkup:
    import urllib.parse

    encoded = urllib.parse.quote(prefill_text)
    url = f"https://t.me/{admin_username}?start={encoded}"
    builder = InlineKeyboardBuilder()
    builder.button(text="✉️ Написать администратору", url=url)
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Subscription status
# ---------------------------------------------------------------------------

def subscription_status_kb(
    has_card: bool,
    auto_renew: bool,
    sub_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить статус", callback_data="sub:refresh")
    if has_card:
        builder.button(text="🗑 Отвязать карту", callback_data="sub:unlink_card")
    if sub_id is not None:
        toggle_text = (
            "⏸ Отключить автопродление" if auto_renew else "▶️ Включить автопродление"
        )
        builder.button(
            text=toggle_text,
            callback_data=f"sub:toggle_renew:{sub_id}:{int(auto_renew)}",
        )
    builder.button(text="⬅️ Главное меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# "Renew" button used in reminders
# ---------------------------------------------------------------------------

def renew_reminder_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Продлить", callback_data="menu:pay")
    builder.adjust(1)
    return builder.as_markup()
