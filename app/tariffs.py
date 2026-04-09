"""Available tariffs."""

from typing import TypedDict


class Tariff(TypedDict):
    code: str
    name: str
    price: int
    currency: str
    duration_months: int
    description: str


TARIFFS: dict[str, Tariff] = {
    "teleport_1m": {
        "code": "teleport_1m",
        "name": "Телепорт 1 мес.",
        "price": 990,
        "currency": "RUB",
        "duration_months": 1,
        "description": (
            "📦 <b>Телепорт — доступ на 1 месяц</b>\n\n"
            "Вы получите персональную ссылку-приглашение в закрытый канал.\n"
            "Ссылка действует сразу после оплаты.\n\n"
            "💳 Стоимость: <b>990 ₽ / месяц</b>"
        ),
    }
}


def get_tariff(code: str) -> Tariff:
    tariff = TARIFFS.get(code)
    if tariff is None:
        raise KeyError(f"Unknown tariff: {code}")
    return tariff
