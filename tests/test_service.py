import pytest

from assistant_bot.service import AssistantService


class ReportStorage:
    async def project_report_data(self, user_id, project_name):
        return {
            "requested_project": project_name,
            "reminders": [
                {"title": "Созвон", "due_at_utc": "2026-09-11T13:30:00+00:00"}
            ],
        }

    async def get_timezone(self, user_id, default):
        return "Asia/Almaty"


class ReportAI:
    def __init__(self):
        self.data = None

    async def make_report(self, data):
        self.data = data
        return "Готово"


class ConversationStorage:
    def __init__(self):
        self.messages = []
        self.memories = []

    async def ensure_user(self, user_id, chat_id, default_timezone):
        return None

    async def get_timezone(self, user_id, default):
        return "Asia/Almaty"

    async def context(self, user_id):
        return {
            "projects": [],
            "memories": [],
            "notes": [],
            "conversation_history": [
                {"role": "user", "content": "Меня зовут Алан"},
                {"role": "assistant", "content": "Запомнил"},
            ],
        }

    async def list_reminders(self, user_id, limit=50):
        return []

    async def add_conversation_message(self, user_id, role, content, source_type="text"):
        self.messages.append((role, content, source_type))

    async def get_or_create_project(self, user_id, name, description):
        return 7 if name else None

    async def save_memory(self, user_id, project_id, fact_key, fact_value, confidence):
        self.memories.append((project_id, fact_key, fact_value, confidence))


class ConversationAI:
    def __init__(self):
        self.context = None

    async def understand(self, text, timezone_name, context):
        self.context = context
        return {"reply": "Тебя зовут Алан.", "actions": []}

    async def extract_memories(self, text, timezone_name, context):
        return [{
            "project": None,
            "fact_key": "предпочитаемый формат ответов",
            "fact_value": "Короткие ответы",
            "confidence": 0.95,
        }]


@pytest.mark.asyncio
async def test_report_includes_local_reminder_time():
    ai = ReportAI()
    service = AssistantService(ReportStorage(), ai, "UTC")

    assert await service.report(1, "Orion") == "Готово"
    assert ai.data["timezone"] == "Asia/Almaty"
    assert ai.data["reminders"][0]["due_at_local"] == "11.09.2026 в 18:30"


@pytest.mark.asyncio
async def test_process_uses_chat_history_and_saves_messages_and_memory():
    storage = ConversationStorage()
    ai = ConversationAI()
    service = AssistantService(storage, ai, "UTC")

    reply = await service.process(1, 10, "Отвечай мне коротко", "text")

    assert reply == "Тебя зовут Алан."
    assert ai.context["conversation_history"][0]["content"] == "Меня зовут Алан"
    assert storage.messages == [
        ("user", "Отвечай мне коротко", "text"),
        ("assistant", "Тебя зовут Алан.", "assistant"),
    ]
    assert storage.memories == [
        (None, "предпочитаемый формат ответов", "Короткие ответы", 0.95)
    ]
