import asyncio
import logging
from contextlib import suppress
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types import MenuButtonWebApp, WebAppInfo

from .ai import AIService
from .config import Settings
from .service import AssistantService
from .storage import Storage
from .time_utils import validate_timezone
from .tunnel import tunnel_supervisor
from .webapp import start_web_server


LOGGER = logging.getLogger(__name__)
HELP_TEXT = """Я персональный помощник с голосом, проектами и точными напоминаниями.

Можно просто отправить голосовое или написать:
• «Завтра в 10 напомни позвонить Данияру»
• «Каждую пятницу в 18:00 присылай отчет по проекту Orion»
• «В проекте Orion решили запустить тест 20 сентября»

Команды:
/reminders — ближайшие напоминания
/cancel 12 — отменить напоминание
/projects — проекты
/report [проект] — отчет
/memory — что я помню
/timezone Asia/Almaty — часовой пояс
/forgetme CONFIRM — удалить всю память и напоминания
/help — помощь"""


def build_dispatcher(settings: Settings, storage: Storage, ai: AIService) -> Dispatcher:
    router = Router()
    service = AssistantService(storage, ai, settings.default_timezone)

    async def guard(message: Message) -> bool:
        if not message.from_user:
            return False
        if settings.allowed_user_ids:
            is_allowed = message.from_user.id in settings.allowed_user_ids
        else:
            is_allowed = await storage.claim_or_check_owner(message.from_user.id)
        if is_allowed:
            return True
        await message.answer("Этот помощник приватный.")
        return False

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if not await guard(message):
            return
        await storage.ensure_user(message.from_user.id, message.chat.id, settings.default_timezone)
        webapp_url = settings.webapp_url or await storage.get_app_setting("webapp_url")
        keyboard = None
        if webapp_url:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="Открыть WIMAX", web_app=WebAppInfo(url=webapp_url)
                )
            ]])
        await message.answer(
            "Привет! Я WIMAX — твой персональный AI‑помощник. 👋\n\n"
            "Можешь написать или отправить голосовое — я создам напоминание, "
            "сохраню заметку в проект и подготовлю отчёт.\n\n" + HELP_TEXT,
            reply_markup=keyboard,
        )

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        if await guard(message):
            await message.answer(HELP_TEXT)

    @router.message(Command("reminders"))
    async def reminders(message: Message) -> None:
        if await guard(message):
            await message.answer(await service.reminder_list_text(message.from_user.id))

    @router.message(Command("projects"))
    async def projects(message: Message) -> None:
        if await guard(message):
            await message.answer(await service.project_list_text(message.from_user.id))

    @router.message(Command("memory"))
    async def memory(message: Message) -> None:
        if await guard(message):
            await message.answer(await service.memory_text(message.from_user.id))

    @router.message(Command("report"))
    async def report(message: Message, command: CommandObject) -> None:
        if not await guard(message):
            return
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        await message.answer(await service.report(message.from_user.id, command.args))

    @router.message(Command("cancel"))
    async def cancel(message: Message, command: CommandObject) -> None:
        if not await guard(message):
            return
        try:
            reminder_id = int((command.args or "").strip())
        except ValueError:
            await message.answer("Укажи номер: /cancel 12")
            return
        ok = await storage.cancel_reminder(message.from_user.id, reminder_id)
        await message.answer("Напоминание отменено." if ok else "Активное напоминание не найдено.")

    @router.message(Command("timezone"))
    async def timezone_command(message: Message, command: CommandObject) -> None:
        if not await guard(message):
            return
        if not command.args:
            current = await storage.get_timezone(message.from_user.id, settings.default_timezone)
            await message.answer("Текущий часовой пояс: " + current)
            return
        try:
            timezone_name = validate_timezone(command.args.strip())
        except ValueError:
            await message.answer("Не узнал пояс. Пример: /timezone Asia/Almaty")
            return
        await storage.set_timezone(message.from_user.id, timezone_name)
        await message.answer("Часовой пояс сохранён: " + timezone_name)

    @router.message(Command("forgetme"))
    async def forget_me(message: Message, command: CommandObject) -> None:
        if not await guard(message):
            return
        if (command.args or "").strip() != "CONFIRM":
            await message.answer(
                "Это навсегда удалит историю диалога, память, проекты, заметки и напоминания. "
                "Для подтверждения отправь /forgetme CONFIRM"
            )
            return
        await storage.delete_user_data(message.from_user.id)
        await message.answer(
            "Удалил историю диалога, память, проекты, заметки и напоминания."
        )

    async def handle_text(message: Message, text: str, source_type: str) -> None:
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            reply = await service.process(
                message.from_user.id, message.chat.id, text, source_type
            )
            await message.answer(reply or "Готово.")
        except Exception:
            LOGGER.exception("Failed to process user message")
            await message.answer("Не получилось обработать сообщение. Попробуй ещё раз через минуту.")

    @router.message(F.voice | F.audio)
    async def voice(message: Message) -> None:
        if not await guard(message):
            return
        media = message.voice or message.audio
        if media.file_size and media.file_size > 20 * 1024 * 1024:
            await message.answer("Файл больше 20 МБ. Отправь более короткую запись.")
            return
        status = await message.answer("🎧 Слушаю…")
        try:
            await message.bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
            stream = await message.bot.download(media)
            if stream is None:
                raise RuntimeError("Telegram returned no audio")
            filename = "voice.ogg" if message.voice else (message.audio.file_name or "audio.mp3")
            transcript = await ai.transcribe(stream.read(), filename)
            await status.edit_text("📝 «{}»".format(transcript[:800]))
            await handle_text(message, transcript, "voice")
        except Exception:
            LOGGER.exception("Voice processing failed")
            await status.edit_text("Не смог разобрать аудио. Попробуй записать ещё раз чуть ближе к микрофону.")

    @router.message(F.text)
    async def text_message(message: Message) -> None:
        if await guard(message):
            await handle_text(message, message.text, "text")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def reminder_worker(bot: Bot, storage: Storage, ai: AIService) -> None:
    service = AssistantService(storage, ai, "Asia/Almaty")
    while True:
        try:
            for reminder in await storage.claim_due_reminders():
                try:
                    if reminder["reminder_kind"] == "project_report":
                        report = await service.report(reminder["user_id"], reminder.get("project_name"))
                        text = "📊 {}\n\n{}".format(reminder["title"], report)
                    else:
                        text = "⏰ Напоминание\n\n{}".format(reminder["title"])
                    await bot.send_message(reminder["chat_id"], text)
                    await storage.mark_delivered(reminder)
                except Exception as exc:
                    LOGGER.exception("Reminder delivery failed: %s", reminder["id"])
                    await storage.mark_failed(reminder["id"], str(exc))
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Reminder worker iteration failed")
        await asyncio.sleep(2)


async def run_bot(settings: Settings) -> None:
    storage = Storage(settings.database_path)
    await storage.initialize()
    ai = AIService(settings.openai_api_key, settings.text_model, settings.transcribe_model)
    bot = Bot(settings.telegram_token)
    dispatcher = build_dispatcher(settings, storage, ai)
    await bot.set_my_commands([
        BotCommand(command="reminders", description="Ближайшие напоминания"),
        BotCommand(command="projects", description="Мои проекты"),
        BotCommand(command="report", description="Отчёт по проекту"),
        BotCommand(command="memory", description="Что помощник помнит"),
        BotCommand(command="help", description="Помощь"),
    ])
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть WIMAX", web_app=WebAppInfo(url=settings.webapp_url)
            )
        )
    worker = asyncio.create_task(reminder_worker(bot, storage, ai))
    web_runner = await start_web_server(settings, storage, ai)
    tunnel_task = None
    if not settings.webapp_url:
        tunnel_task = asyncio.create_task(
            tunnel_supervisor(bot, storage, settings.webapp_port)
        )
    try:
        await dispatcher.start_polling(bot)
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        if tunnel_task:
            tunnel_task.cancel()
            with suppress(asyncio.CancelledError):
                await tunnel_task
        await web_runner.cleanup()
        await bot.session.close()
