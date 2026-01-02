# Tepthon Telegram Bot

## Overview

This is an Arabic-language Telegram bot built with pyTelegramBotAPI and Telethon. The bot provides AI-powered responses using the Groq API (Mixtral model) and supports multi-account session management. It includes admin controls, mandatory channel subscription verification, and runs a Flask web server to keep the bot alive on hosting platforms.

**Core Features:**
- AI-powered chat responses via Groq API
- Telethon user session management (users can add their Telegram accounts)
- Mandatory channel subscription before using the bot
- Admin panel for bot control and user permission management
- Flask health-check endpoint for uptime monitoring

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework Architecture
- **Primary Bot Library**: pyTelegramBotAPI (telebot) for handling bot commands and callbacks
- **Secondary Library**: Telethon for managing user client sessions with StringSession authentication
- **Async Handling**: Uses asyncio event loop in separate threads to run Telethon clients alongside the synchronous telebot

### Component Structure
| File | Purpose |
|------|---------|
| `main.py` | Entry point - imports and runs the bot |
| `bot.py` | Core bot logic, command handlers, session management |
| `Professional.py` | Groq AI integration for generating responses |
| `DevAhmed.py` | Admin control panel and permission management |
| `Must_Join.py` | Channel subscription verification |
| `wed.py` | Flask web server for health checks |

### Admin System
- Hardcoded admin user IDs in `DevAhmed.py`
- Admin commands: `/TEP` (control panel), `/Tepvip` (grant access), `/TepDelete` (revoke access)
- Reply keyboard markup for admin actions

### Subscription Gate Pattern
- Users must join specified Telegram channels before using the bot
- Channels configured in `Must_Join.py` as a list
- Bot checks membership status via `get_chat_member` API

### Session Management
- Users can add Telegram accounts via StringSession tokens
- Sessions stored in memory dictionary (`sessions`)
- Each user client runs in its own thread with dedicated event loop
- Auto-replies to group messages using AI responses

## External Dependencies

### APIs & Services
| Service | Purpose | Configuration |
|---------|---------|---------------|
| Telegram Bot API | Primary bot interface | `BOT_TOKEN` env var |
| Telegram MTProto API | User client sessions | `API_ID`, `API_HASH` env vars |
| Groq API | AI text generation (Mixtral-8x7b-32768) | `GROQ_API_KEY` env var |

### Required Telegram Channels
- `@Tepthon` - Main channel
- `@TepthonHelp` - Support channel

### Database
- `psycopg2-binary` and `sqlalchemy` are in requirements but not yet implemented in code
- Prepared for future PostgreSQL integration for persistent session/user storage

### Environment Variables Required
```
BOT_TOKEN - Telegram bot token from @BotFather
API_ID - Telegram API ID from my.telegram.org
API_HASH - Telegram API hash from my.telegram.org
GROQ_API_KEY - API key for Groq AI service
```

### Python Packages
- `pytelegrambotapi` - Synchronous Telegram bot framework
- `telethon` - Async Telegram client library
- `flask` - Web server for health checks
- `groq` - Groq AI API client
- `python-dotenv` - Environment variable loading
- `sqlalchemy` / `psycopg2-binary` - Database (prepared, not implemented)