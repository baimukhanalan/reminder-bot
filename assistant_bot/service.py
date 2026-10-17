import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .ai import AIService
from .storage import Storage
from .time_utils import display_datetime, parse_model_datetime, utc_now


LOGGER = logging.getLogger(__name__)


class AssistantService:
    def __init__(self, storage: Storage, ai: AIService, default_timezone: str):
        self.storage = storage
        self.ai = ai
        self.default_timezone = default_timezone

    async def process(
        self, user_id: int, chat_id: int, text: str, source_type: str
    ) -> str:
        await self.storage.ensure_user(user_id, chat_id, self.default_timezone)
        tz = await self.storage.get_timezone(user_id, self.default_timezone)
        context = await self.storage.context(user_id)
        context["upcoming_reminders"] = await self.storage.list_reminders(user_id, 15)
        await self.storage.add_conversation_message(user_id, "user", text, source_type)

        async def extract_memories() -> List[Dict[str, Any]]:
            extractor = getattr(self.ai, "extract_memories", None)
            if extractor is None:
                return []
            try:
                return await extractor(text, tz, context)
            except Exception:
                LOGGER.exception("Personal memory extraction failed")
                return []

        result, extracted_memories = await asyncio.gather(
            self.ai.understand(text, tz, context),
            extract_memories(),
        )
        confirmations: List[str] = []
        saved_memory_keys = set()

        for action in result.get("actions", []):
            project_id = await self.storage.get_or_create_project(
                user_id,
                action.get("project"),
                action.get("project_description") or "",
            )
            action_type = action.get("type")
            if action_type == "reminder":
                if not action.get("title") or not action.get("due_at"):
                    continue
                due_timezone = action.get("due_timezone") or tz
                try:
                    due_at = parse_model_datetime(action["due_at"], due_timezone)
                except (ValueError, KeyError):
                    confirmations.append("⚠️ Не узнал часовой пояс — уточни город или время.")
                    continue
                now = utc_now()
                if due_at < now:
                    if now - due_at <= timedelta(minutes=2):
                        due_at = now
                    else:
                        confirmations.append("⚠️ Указанное время уже прошло — уточни новое время.")
                        continue
                reminder_id = await self.storage.add_reminder(
                    user_id=user_id,
                    chat_id=chat_id,
                    project_id=project_id,
                    title=action["title"],
                    due_at=due_at,
                    recurrence=action.get("recurrence") or "none",
                    reminder_kind=action.get("reminder_kind") or "notification",
                )
                repeat = {
                    "daily": ", каждый день",
                    "weekly": ", каждую неделю",
                    "monthly": ", каждый месяц",
                }.get(action.get("recurrence"), "")
                confirmations.append(
                    "⏰ Напоминание #{}: {} — {}{}".format(
                        reminder_id, action["title"], display_datetime(due_at.isoformat(), tz), repeat
                    )
                )
            elif action_type == "memory":
                if action.get("fact_key") and action.get("fact_value"):
                    await self.storage.save_memory(
                        user_id, project_id, action["fact_key"], action["fact_value"],
                        float(action.get("confidence") or 0.8),
                    )
                    saved_memory_keys.add(
                        ((action.get("project") or "").casefold(), action["fact_key"].casefold())
                    )
            elif action_type == "note" and action.get("note"):
                await self.storage.add_note(user_id, project_id, action["note"], source_type)
            elif action_type == "cancel_reminder" and action.get("reminder_id"):
                cancelled = await self.storage.cancel_reminder(user_id, action["reminder_id"])
                confirmations.append(
                    "✅ Напоминание отменено." if cancelled else "Не нашёл активное напоминание с таким номером."
                )

        for memory in extracted_memories:
            fact_key = str(memory.get("fact_key") or "").strip()
            fact_value = str(memory.get("fact_value") or "").strip()
            project_name = str(memory.get("project") or "").strip()
            dedupe_key = (project_name.casefold(), fact_key.casefold())
            if not fact_key or not fact_value or dedupe_key in saved_memory_keys:
                continue
            project_id = await self.storage.get_or_create_project(user_id, project_name, "")
            await self.storage.save_memory(
                user_id,
                project_id,
                fact_key,
                fact_value,
                float(memory.get("confidence") or 0.8),
            )
            saved_memory_keys.add(dedupe_key)

        parts = [result.get("reply", "").strip()] + confirmations
        reply = "\n\n".join(part for part in parts if part) or "Готово."
        await self.storage.add_conversation_message(user_id, "assistant", reply, "assistant")
        return reply

    async def reminder_list_text(self, user_id: int) -> str:
        tz = await self.storage.get_timezone(user_id, self.default_timezone)
        rows = await self.storage.list_reminders(user_id)
        if not rows:
            return "Активных напоминаний пока нет."
        lines = ["Ближайшие напоминания:"]
        for row in rows:
            project = " · {}".format(row["project_name"]) if row.get("project_name") else ""
            lines.append(
                "#{} — {} — {}{}".format(
                    row["id"], display_datetime(row["due_at_utc"], tz), row["title"], project
                )
            )
        return "\n".join(lines)

    async def project_list_text(self, user_id: int) -> str:
        context = await self.storage.context(user_id)
        projects = context["projects"]
        if not projects:
            return "Проектов пока нет. Просто расскажи голосом или текстом, над чем работаешь."
        return "Твои проекты:\n" + "\n".join("• " + row["name"] for row in projects)

    async def memory_text(self, user_id: int) -> str:
        context = await self.storage.context(user_id)
        memories = context["memories"]
        if not memories:
            return "Память пока пуста."
        lines = ["Что я помню:"]
        for row in memories:
            project = " [{}]".format(row["project_name"]) if row.get("project_name") else ""
            lines.append("• {}{}: {}".format(row["fact_key"], project, row["fact_value"]))
        return "\n".join(lines)

    async def report(self, user_id: int, project_name: Optional[str]) -> str:
        data = await self.storage.project_report_data(user_id, project_name)
        timezone_name = await self.storage.get_timezone(user_id, self.default_timezone)
        data["timezone"] = timezone_name
        for reminder in data.get("reminders", []):
            reminder["due_at_local"] = display_datetime(
                reminder["due_at_utc"], timezone_name
            )
        return await self.ai.make_report(data)
