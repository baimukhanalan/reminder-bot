from datetime import timedelta

import pytest

from assistant_bot.storage import Storage
from assistant_bot.time_utils import utc_now


@pytest.mark.asyncio
async def test_startup_recovers_claimed_reminder(tmp_path):
    path = tmp_path / "test.db"
    storage = Storage(path)
    await storage.initialize()
    await storage.ensure_user(1, 10, "Asia/Almaty")
    await storage.add_reminder(
        1, 10, None, "Recover me", utc_now() - timedelta(seconds=1), "none", "notification"
    )
    assert len(await storage.claim_due_reminders()) == 1

    restarted = Storage(path)
    await restarted.initialize()
    assert len(await restarted.claim_due_reminders()) == 1
