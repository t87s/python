"""Tests for memory adapter."""

import pytest

from t87s import AsyncMemoryAdapter, CacheEntry, Tag


class TestAsyncMemoryAdapter:
    """Tests for async AsyncMemoryAdapter."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, async_adapter: AsyncMemoryAdapter
    ) -> None:
        """Test that getting a nonexistent key returns None."""
        assert await async_adapter.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, async_adapter: AsyncMemoryAdapter) -> None:
        """Test setting and getting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value={"id": "123"},
            tags=[Tag(("user", "123"))],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        await async_adapter.set("key1", entry)
        result = await async_adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "123"}

    @pytest.mark.asyncio
    async def test_delete(self, async_adapter: AsyncMemoryAdapter) -> None:
        """Test deleting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        await async_adapter.set("key1", entry)
        await async_adapter.delete("key1")
        assert await async_adapter.get("key1") is None

    @pytest.mark.asyncio
    async def test_clear(self, async_adapter: AsyncMemoryAdapter) -> None:
        """Test clearing all entries."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        await async_adapter.set("key1", entry)
        await async_adapter.set("key2", entry)
        await async_adapter.clear()
        assert await async_adapter.get("key1") is None
        assert await async_adapter.get("key2") is None

    @pytest.mark.asyncio
    async def test_tag_invalidation_time(
        self, async_adapter: AsyncMemoryAdapter
    ) -> None:
        """Test setting and getting tag invalidation time."""
        tag = Tag(("user", "123"))
        assert await async_adapter.get_tag_invalidation_time(tag) is None

        await async_adapter.set_tag_invalidation_time(tag, 1000)
        assert await async_adapter.get_tag_invalidation_time(tag) == 1000

    @pytest.mark.asyncio
    async def test_lru_eviction(self) -> None:
        """Test LRU eviction when max_items is set."""
        adapter = AsyncMemoryAdapter(max_items=2)
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )

        await adapter.set("key1", entry)
        await adapter.set("key2", entry)
        await adapter.set("key3", entry)  # Should evict key1

        assert await adapter.get("key1") is None
        assert await adapter.get("key2") is not None
        assert await adapter.get("key3") is not None
