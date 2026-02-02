"""Tests for .entries access on query results."""

import pytest

from t87s import AsyncMemoryAdapter, QueryCache, TagSchema, Wild, cached


class UserTags(TagSchema):
    users: Wild[TagSchema]


class TestEntriesAccess:
    """Tests for .entries property on query results."""

    @pytest.fixture
    def cache(self) -> QueryCache[UserTags]:
        class TestCache(QueryCache[UserTags]):
            @cached(UserTags.users())
            async def get_user(self, user_id: str) -> dict[str, str]:
                return {"id": user_id, "name": "Test"}

        return TestCache(adapter=AsyncMemoryAdapter())

    async def test_direct_await_returns_value(
        self, cache: QueryCache[UserTags]
    ) -> None:
        """Direct await returns the value."""
        user = await cache.get_user("123")
        assert user == {"id": "123", "name": "Test"}

    async def test_entries_returns_cache_metadata(
        self, cache: QueryCache[UserTags]
    ) -> None:
        """Accessing .entries returns EntriesResult with cache metadata."""
        result = await cache.get_user("123").entries
        assert result.before is None  # First call is a miss
        assert result.after.value == {"id": "123", "name": "Test"}

    async def test_entries_returns_same_entry_on_hit(
        self, cache: QueryCache[UserTags]
    ) -> None:
        """On cache hit, before and after are the same entry."""
        # Populate cache
        await cache.get_user("123")

        # Check entries
        result = await cache.get_user("123").entries
        assert result.before is not None
        assert result.before is result.after

    async def test_entries_value_accessible(self, cache: QueryCache[UserTags]) -> None:
        """Can access value through entries result."""
        result = await cache.get_user("123").entries
        assert result.after.value["name"] == "Test"
