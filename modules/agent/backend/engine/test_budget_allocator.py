"""Tests for budget_allocator.py — diminishing returns tracker + context assembly.

All tests use an in-memory store instead of the database by overriding
``_load_from_db`` / ``_save_to_db`` on the tracker instance.  This keeps
tests fast, self-contained, and free of cross-test state leakage.
"""
import pytest
from .budget_allocator import DiminishingBudgetTracker, DiminishingReturnRecord


class TestDiminishingBudgetTracker:
    """In-memory backed tests for DiminishingBudgetTracker.

    The ``tracker`` fixture replaces the DB persistence layer with an
    in-memory dict so the tests do not need a real database session.
    """

    @pytest.fixture
    def tracker(self):
        """Create a DiminishingBudgetTracker with in-memory storage."""
        store: dict[str, list[dict]] = {}

        async def mock_load(db, session_key):
            return store.get(session_key, [])

        async def mock_save(db, session_key, owner_id, records):
            store[session_key] = records

        async def mock_reset(db, session_key):
            store.pop(session_key, None)

        t = DiminishingBudgetTracker()
        t._load_from_db = mock_load
        t._save_to_db = mock_save
        t.reset = mock_reset
        return t

    @pytest.mark.asyncio
    async def test_no_stop_before_min_rounds(self, tracker):
        should_stop, reason = await tracker.should_stop(None, "test_1")
        assert should_stop is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_no_stop_with_high_gains(self, tracker):
        for i in range(5):
            await tracker.record_round(None, "test_2", 0,
                tokens_before=i * 1000, tokens_after=(i + 1) * 1000)
        should_stop, reason = await tracker.should_stop(None, "test_2")
        assert should_stop is False

    @pytest.mark.asyncio
    async def test_stop_on_low_gains(self, tracker):
        for i in range(5):
            await tracker.record_round(None, "test_3", 0,
                tokens_before=i * 1000, tokens_after=i * 1000 + 100)
        should_stop, reason = await tracker.should_stop(None, "test_3")
        assert should_stop is True
        assert "收益递减" in reason
        assert "净增" in reason

    @pytest.mark.asyncio
    async def test_stop_on_monotonic_decline(self, tracker):
        await tracker.record_round(None, "test_4", 0, tokens_before=0, tokens_after=2000)
        await tracker.record_round(None, "test_4", 0, tokens_before=2000, tokens_after=3000)
        await tracker.record_round(None, "test_4", 0, tokens_before=3000, tokens_after=3400)
        await tracker.record_round(None, "test_4", 0, tokens_before=3400, tokens_after=3600)
        should_stop, reason = await tracker.should_stop(None, "test_4")
        assert should_stop is True
        assert "单调下降" in reason

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, tracker):
        await tracker.record_round(None, "test_5", 0, tokens_before=0, tokens_after=100)
        await tracker.record_round(None, "test_5", 0, tokens_before=100, tokens_after=150)
        await tracker.record_round(None, "test_5", 0, tokens_before=150, tokens_after=180)
        await tracker.reset(None, "test_5")
        should_stop, reason = await tracker.should_stop(None, "test_5")
        assert should_stop is False
        assert reason == ""

    @pytest.mark.asyncio
    async def test_get_diagnosis(self, tracker):
        await tracker.record_round(None, "test_6", 0, tokens_before=0, tokens_after=1000)
        await tracker.record_round(None, "test_6", 0, tokens_before=1000, tokens_after=1500)
        diag = await tracker.get_diagnosis(None, "test_6")
        assert diag["total_rounds"] == 2
        assert diag["recent_gains"] == [1000, 500]

    @pytest.mark.asyncio
    async def test_net_gain_never_negative(self, tracker):
        rec = await tracker.record_round(None, "test_7", 0,
            tokens_before=1000, tokens_after=800)
        assert rec.net_gain_tokens >= 0
