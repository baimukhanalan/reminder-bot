<div align="center">

# 🎙️ Reminder Bot

### A voice-first Telegram assistant — capture reminders by voice, organize projects, never forget

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-aiosqlite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-powered-412991?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](#-license)

</div>

## 📖 About

Reminder Bot is a personal Telegram assistant built around your voice. Send a voice
message — or type — and it transcribes the audio, extracts a precise reminder, files the
note under the right project, and quietly remembers useful context for later. It understands
mixed Russian, Kazakh, and English, and replies in the user's language.

The assistant ships with a Telegram **Mini App**: a full workspace inside Telegram with a
central microphone button, a timeline of upcoming reminders, project notes with AI reports,
a searchable knowledge base, and a transparent view of everything the bot has memorized.

It is a small but complete project: an async Telegram bot, a persistent reminder worker, an
aiohttp API, and a React mini app — all in one deployable unit.

## ✨ Features

- 🎤 **Voice reminders** — send voice or audio (up to 20 MB); OpenAI transcription turns speech into exact, scheduled reminders.
- ⏰ **Precise scheduling** — one-off, daily, weekly, and monthly recurrence, with per-user timezones.
- 🗂️ **Projects** — notes and tasks are auto-organized into projects, each with on-demand or scheduled AI reports.
- 🧠 **Long-term memory** — the bot learns durable facts and preferences; `/memory` shows them and `/forgetme` wipes everything.
- 🔔 **Reliable notifications** — a background worker delivers due reminders and survives restarts via SQLite; anything missed while offline is sent on next start.
- 📱 **Telegram Mini App** — Today timeline, Projects, Base (search), and Memory tabs, with a voice-capture sheet.
- 🔒 **Private by design** — allow-list specific Telegram IDs, or let the first user become the sole owner; the Mini App verifies signed `initData`.

## 🛠️ Tech Stack

| Layer      | Technology                                             |
| ---------- | ------------------------------------------------------ |
| Language   | Python 3.9+                                             |
| Bot        | [aiogram 3](https://docs.aiogram.dev/)                 |
| Web / API  | [aiohttp](https://docs.aiohttp.org/)                   |
| Storage    | SQLite via [aiosqlite](https://github.com/omnilib/aiosqlite) |
| AI         | [OpenAI](https://platform.openai.com/) (transcription + reasoning) |
| Mini App   | React + TypeScript + Vite                              |
| Packaging  | `pyproject.toml`, Docker                               |

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+ (to build the Mini App)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- An OpenAI API key

### Installation

```bash
git clone https://github.com/<your-username>/reminder-bot.git
cd reminder-bot

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# Build the Telegram Mini App
cd webapp && npm install && npm run build && cd ..
```

### Configuration

Copy `.env.example` to `.env.local` and fill in your secrets (`.env.local` is git-ignored):

```dotenv
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
OPENAI_API_KEY=<your-openai-api-key>
DEFAULT_TIMEZONE=Asia/Almaty
DATABASE_PATH=data/assistant.db
# Optional: comma-separated owner IDs. Empty = first user becomes owner.
ALLOWED_TELEGRAM_USER_IDS=
# Public HTTPS URL for the Mini App button (auto-tunneled in dev if empty).
WEBAPP_URL=
WEBAPP_PORT=8080
```

### Run

```bash
python -m assistant_bot.main   # or: reminder-bot
```

### Run with Docker

```bash
docker build -t reminder-bot .
docker run --rm \
  -e TELEGRAM_BOT_TOKEN=<your-telegram-bot-token> \
  -e OPENAI_API_KEY=<your-openai-api-key> \
  -v "$(pwd)/data:/app/data" \
  reminder-bot
```

> The process should run continuously (VPS, Railway, Docker). Run a single instance at a time;
> reminders due while it was offline are delivered right after the next start.

## 📂 Project Structure

```
reminder-bot/
├── assistant_bot/        # Python package
│   ├── bot.py            # aiogram handlers, commands, reminder worker
│   ├── ai.py             # OpenAI transcription, understanding, reports
│   ├── service.py        # Orchestration between AI and storage
│   ├── storage.py        # aiosqlite persistence layer
│   ├── webapp.py         # aiohttp API for the Mini App
│   ├── web_auth.py       # Telegram initData signature validation
│   ├── config.py         # Environment-based settings
│   └── main.py           # Entry point
├── webapp/               # React + TypeScript + Vite Mini App
├── tests/                # pytest suite
├── Dockerfile
└── pyproject.toml
```

## 🗺️ Roadmap

- [ ] Automated reminder snooze and reschedule from the Mini App
- [ ] Shared projects across multiple users
- [ ] Calendar (ICS) export and import
- [ ] Richer analytics in project reports
- [ ] Optional alternative transcription / LLM providers

## 📄 License

Released under the [MIT License](LICENSE).
