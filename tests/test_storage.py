from datetime import timedelta

import pytest

from assistant_bot.storage import Storage
from assistant_bot.time_utils import utc_now


@pytest.mark.asyncio
async def test_reminder_claim_and_delivery(tmp_path):
    storage = Storage(tmp_path / "test.db")
    await storage.initialize()
    await storage.ensure_user(1, 10, "Asia/Almaty")
    reminder_id = await storage.add_reminder(
        1, 10, None, "Test", utc_now() - timedelta(seconds=1), "none", "notification"
    )
    due = await storage.claim_due_reminders()
    assert [item["id"] for item in due] == [reminder_id]
    await storage.mark_delivered(due[0])
    assert await storage.claim_due_reminders() == []


@pytest.mark.asyncio
async def test_user_data_is_isolated(tmp_path):
    storage = Storage(tmp_path / "test.db")
    await storage.initialize()
    await storage.ensure_user(1, 10, "Asia/Almaty")
    await storage.ensure_user(2, 20, "Asia/Almaty")
    await storage.add_reminder(1, 10, None, "Private", utc_now(), "none", "notification")
    assert len(await storage.list_reminders(1)) == 1
    assert await storage.list_reminders(2) == []


@pytest.mark.asyncio
async def test_conversation_history_persists_is_bounded_and_cascades(tmp_path):
    storage = Storage(tmp_path / "test.db")
    await storage.initialize()
    await storage.ensure_user(1, 10, "Asia/Almaty")
    await storage.ensure_user(2, 20, "Asia/Almaty")

    await storage.add_conversation_message(1, "user", "Первое")
    await storage.add_conversation_message(1, "assistant", "Второе", "assistant")
    await storage.add_conversation_message(1, "user", "Третье")

    history = await storage.conversation_history(1, limit=2)
    assert [(row["role"], row["content"]) for row in history] == [
        ("assistant", "Второе"),
        ("user", "Третье"),
    ]
    assert await storage.conversation_history(2) == []

    await storage.delete_user_data(1)
    assert await storage.conversation_history(1) == []
