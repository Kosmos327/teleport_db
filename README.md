# teleport_db

Production-grade Telegram bot refactoring: Google Sheets → PostgreSQL.

## Stack
- **Python 3.12**
- **aiogram 3** — Telegram Bot API
- **aiohttp** — webhook server
- **SQLAlchemy 2 (async) + asyncpg** — PostgreSQL ORM
- **Alembic** — database migrations
- **YooKassa SDK** — payment processing
- **APScheduler** — subscription reminders & auto-renewal
- **pydantic-settings** — configuration

## Project structure

```
app/
├── config.py               # Settings (pydantic-settings, .env)
├── tariffs.py              # Tariff definitions
├── main.py                 # Entry point (webhook or polling)
├── middleware.py           # DB session middleware (aiogram 3)
├── scheduler.py            # APScheduler: reminders + autopay
├── database/
│   ├── models.py           # SQLAlchemy ORM models
│   └── session.py          # Async engine + session factory
├── repositories/           # CRUD layer for every model
│   ├── users.py
│   ├── payments.py
│   ├── payment_methods.py
│   ├── subscriptions.py
│   ├── invite_links.py
│   └── event_logs.py
├── handlers/               # aiogram handlers (FSM)
│   ├── start.py            # /start, consent
│   ├── tariff.py           # Tariff selection
│   ├── email_handler.py    # Email collection
│   ├── payment.py          # Payment confirmation
│   └── subscription.py     # Subscription status
├── services/
│   ├── payment_service.py  # YooKassa API wrappers (async)
│   └── invite_service.py   # Telegram invite link creation
├── states/
│   └── states.py           # FSM states
├── keyboards/
│   └── keyboards.py        # All inline keyboards
├── utils/
│   └── dt.py               # Timezone utils (now_local, add_months_keep_day)
└── webhook/
    └── yookassa_webhook.py # aiohttp handler for YooKassa notifications

alembic/                    # Database migrations
alembic.ini
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Database schema

| Table | Description |
|-------|-------------|
| `users` | Telegram users (id, username, first_name, email) |
| `payments` | YooKassa payment records |
| `payment_methods` | Saved cards for auto-renewal |
| `subscriptions` | Subscription periods with status |
| `invite_links` | Issued Telegram invite links log |
| `event_logs` | Technical event journal (JSONB payload) |

## Quick start

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run with Docker Compose

```bash
docker-compose up -d
```

### 3. Run migrations (first time)

```bash
docker-compose exec bot alembic upgrade head
```

### 4. Local development (polling mode)

Leave `WEBHOOK_HOST` empty in `.env`, then:

```bash
pip install -r requirements.txt
python -m app.main
```

## Configuration reference

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` |
| `YOOKASSA_SHOP_ID` | YooKassa shop ID |
| `YOOKASSA_SECRET_KEY` | YooKassa secret key |
| `YOOKASSA_RETURN_URL` | Redirect URL after payment |
| `TIMEZONE` | Timezone for datetimes (default: `Europe/Moscow`) |
| `ADMIN_IDS` | JSON array of admin Telegram IDs |
| `ADMIN_USERNAME` | Admin username (without @) |
| `ACCESS_CHAT_ID` | Closed chat ID to issue invite links for |
| `WEBHOOK_HOST` | Public HTTPS URL (empty = polling mode) |
| `BOT_WEBHOOK_PATH` | Path for Telegram webhook (default: `/webhook/bot`) |
| `YOOKASSA_WEBHOOK_PATH` | Path for YooKassa webhook (default: `/webhook/yookassa`) |
| `WEBAPP_PORT` | HTTP server port (default: `8080`) |

## Deploying to Timeweb App Platform

1. Push to GitHub
2. Create a new App in Timeweb App Platform, connect the repository
3. Set all environment variables from `.env.example`
4. Timeweb will build the Docker image and expose port 8080
5. Set `WEBHOOK_HOST` to the assigned domain (e.g. `https://your-app.timeweb.app`)
6. Run the initial migration via the app console: `alembic upgrade head`

## FSM states

| State | Description |
|-------|-------------|
| `waiting_start` | Consent screen |
| `main` | Main menu |
| `choosing_tariff` | Tariff selection |
| `waiting_email` | Collecting email for receipt |
| `preview` | Payment confirmation screen |

## YooKassa webhook events handled

- `payment.succeeded` → update payment, create subscription, issue invite link, notify user
- `payment.canceled` → update payment status

## Scheduler jobs

- **Daily 09:00** — pre-notice reminders for subscriptions expiring within `PRENOTICE_DAYS` days (default: 3)
- **Hourly** — auto-renewal for cards whose `next_charge_at` has passed
