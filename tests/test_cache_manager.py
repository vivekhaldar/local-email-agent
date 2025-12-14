# ABOUTME: Tests for cache_manager.py
# ABOUTME: Tests cache key generation, storage, lookup, and stats

import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cache_manager import (
    get_cache_key,
    init_cache_db,
    lookup_cache,
    save_to_cache,
    get_cache_stats,
    clear_cache,
)


class TestGetCacheKey:
    """Tests for get_cache_key() function."""

    def test_single_email(self):
        """Single email uses msg: prefix."""
        item = {
            "is_thread": False,
            "messages": [{"message_num": 12345}]
        }
        assert get_cache_key(item) == "msg:12345"

    def test_thread_sorted_message_nums(self):
        """Thread uses sorted message nums."""
        item = {
            "is_thread": True,
            "messages": [
                {"message_num": 300},
                {"message_num": 100},
                {"message_num": 200}
            ]
        }
        assert get_cache_key(item) == "thread:100-200-300"

    def test_thread_new_message_changes_key(self):
        """Adding a message to thread changes the key."""
        item1 = {
            "is_thread": True,
            "messages": [
                {"message_num": 100},
                {"message_num": 200}
            ]
        }
        item2 = {
            "is_thread": True,
            "messages": [
                {"message_num": 100},
                {"message_num": 200},
                {"message_num": 300}
            ]
        }
        key1 = get_cache_key(item1)
        key2 = get_cache_key(item2)
        assert key1 != key2
        assert key1 == "thread:100-200"
        assert key2 == "thread:100-200-300"

    def test_empty_messages_returns_empty(self):
        """Empty messages list returns empty key."""
        item = {"is_thread": False, "messages": []}
        assert get_cache_key(item) == ""

    def test_no_messages_key_returns_empty(self):
        """Missing messages key returns empty key."""
        item = {"is_thread": False}
        assert get_cache_key(item) == ""


class TestCacheOperations:
    """Tests for cache database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = Path(f.name)
        init_cache_db(db_path)
        yield db_path
        db_path.unlink(missing_ok=True)

    def test_lookup_nonexistent_returns_none(self, temp_db):
        """Looking up a non-existent key returns None."""
        result = lookup_cache("msg:99999", temp_db)
        assert result is None

    def test_save_and_lookup(self, temp_db):
        """Saving and looking up a cache entry works."""
        save_to_cache(
            cache_key="msg:12345",
            category="FYI",
            summary="Test summary",
            action_items=None,
            cost_usd=0.001,
            db_path=temp_db
        )

        result = lookup_cache("msg:12345", temp_db)
        assert result is not None
        assert result["category"] == "FYI"
        assert result["summary"] == "Test summary"
        assert result["action_items"] is None
        assert result["cost_usd"] == 0.001
        assert result["from_cache"] is True

    def test_save_with_action_items(self, temp_db):
        """Saving with action items preserves them."""
        save_to_cache(
            cache_key="msg:111",
            category="NEEDS_RESPONSE",
            summary="Please reply",
            action_items="Reply by Friday",
            cost_usd=0.002,
            db_path=temp_db
        )

        result = lookup_cache("msg:111", temp_db)
        assert result["action_items"] == "Reply by Friday"

    def test_save_overwrites_existing(self, temp_db):
        """Saving with same key overwrites existing entry."""
        save_to_cache(
            cache_key="msg:222",
            category="FYI",
            summary="Original",
            action_items=None,
            cost_usd=0.001,
            db_path=temp_db
        )
        save_to_cache(
            cache_key="msg:222",
            category="URGENT",
            summary="Updated",
            action_items="Do now",
            cost_usd=0.002,
            db_path=temp_db
        )

        result = lookup_cache("msg:222", temp_db)
        assert result["category"] == "URGENT"
        assert result["summary"] == "Updated"
        assert result["action_items"] == "Do now"

    def test_lookup_nonexistent_db_returns_none(self):
        """Looking up in non-existent database returns None."""
        result = lookup_cache("msg:123", Path("/nonexistent/path.sqlite"))
        assert result is None


class TestCacheStats:
    """Tests for cache statistics."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = Path(f.name)
        init_cache_db(db_path)
        yield db_path
        db_path.unlink(missing_ok=True)

    def test_empty_cache_stats(self, temp_db):
        """Empty cache returns zero stats."""
        stats = get_cache_stats(temp_db)
        assert stats["total_entries"] == 0
        assert stats["total_cost_usd"] == 0.0

    def test_stats_after_entries(self, temp_db):
        """Stats reflect saved entries."""
        save_to_cache("msg:1", "FYI", "Sum1", None, 0.001, db_path=temp_db)
        save_to_cache("msg:2", "URGENT", "Sum2", None, 0.002, db_path=temp_db)
        save_to_cache("msg:3", "FYI", "Sum3", None, 0.003, db_path=temp_db)

        stats = get_cache_stats(temp_db)
        assert stats["total_entries"] == 3
        assert abs(stats["total_cost_usd"] - 0.006) < 0.0001

    def test_nonexistent_db_stats(self):
        """Non-existent database returns zero stats."""
        stats = get_cache_stats(Path("/nonexistent/path.sqlite"))
        assert stats["total_entries"] == 0


class TestClearCache:
    """Tests for cache clearing."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = Path(f.name)
        init_cache_db(db_path)
        yield db_path
        db_path.unlink(missing_ok=True)

    def test_clear_empty_cache(self, temp_db):
        """Clearing empty cache returns 0."""
        count = clear_cache(temp_db)
        assert count == 0

    def test_clear_populated_cache(self, temp_db):
        """Clearing populated cache returns count and empties."""
        save_to_cache("msg:1", "FYI", "Sum1", None, 0.001, db_path=temp_db)
        save_to_cache("msg:2", "FYI", "Sum2", None, 0.001, db_path=temp_db)

        count = clear_cache(temp_db)
        assert count == 2

        # Verify empty
        stats = get_cache_stats(temp_db)
        assert stats["total_entries"] == 0

    def test_clear_nonexistent_db(self):
        """Clearing non-existent database returns 0."""
        count = clear_cache(Path("/nonexistent/path.sqlite"))
        assert count == 0
