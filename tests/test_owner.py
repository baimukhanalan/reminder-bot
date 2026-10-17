import pytest

from assistant_bot.storage import Storage


@pytest.mark.asyncio
async def test_first_user_claims_unconfigured_bot(tmp_path):
    storage = Storage(tmp_path / "test.db")
    await storage.initialize()
    assert await storage.claim_or_check_owner(111)
    assert await storage.claim_or_check_owner(111)
    assert not await storage.claim_or_check_owner(222)
