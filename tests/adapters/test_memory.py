"""Tests for memory adapters."""

from t87s import AsyncMemoryAdapter, CacheEntry, MemoryAdapter, Tag


class TestMemoryAdapter:
    """Tests for sync MemoryAdapter."""

    def test_get_nonexistent_returns_none(self, adapter: MemoryAdapter) -> None:
        """Test that getting a nonexistent key returns None."""
        assert adapter.get("nonexistent") is None

    def test_set_and_get(self, adapter: MemoryAdapter) -> None:
        """Test setting and getting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value={"id": "123"},
            tags=[Tag(("user", "123"))],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        adapter.set("key1", entry)
        result = adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "123"}

    def test_delete(self, adapter: MemoryAdapter) -> None:
        """Test deleting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        adapter.set("key1", entry)
        adapter.delete("key1")
        assert adapter.get("key1") is None

    def test_delete_nonexistent(self, adapter: MemoryAdapter) -> None:
        """Test that deleting a nonexistent key doesn't raise."""
        adapter.delete("nonexistent")  # Should not raise

    def test_clear(self, adapter: MemoryAdapter) -> None:
        """Test clearing all entries."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )
        adapter.set("key1", entry)
        adapter.set("key2", entry)
        adapter.clear()
        assert adapter.get("key1") is None
        assert adapter.get("key2") is None

    def test_tag_invalidation_time(self, adapter: MemoryAdapter) -> None:
        """Test setting and getting tag invalidation time."""
        tag = Tag(("user", "123"))
        assert adapter.get_tag_invalidation_time(tag) is None

        adapter.set_tag_invalidation_time(tag, 1000)
        assert adapter.get_tag_invalidation_time(tag) == 1000

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when max_items is set."""
        adapter = MemoryAdapter(max_items=2)
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )

        adapter.set("key1", entry)
        adapter.set("key2", entry)
        adapter.set("key3", entry)  # Should evict key1

        assert adapter.get("key1") is None
        assert adapter.get("key2") is not None
        assert adapter.get("key3") is not None

    def test_lru_access_updates_order(self) -> None:
        """Test that accessing an item updates its LRU order."""
        adapter = MemoryAdapter(max_items=2)
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=2000,
            grace_until=None,
        )

        adapter.set("key1", entry)
        adapter.set("key2", entry)
        adapter.get("key1")  # Access key1 to make it most recently used
        adapter.set("key3", entry)  # Should evict key2, not key1

        assert adapter.get("key1") is not None
        assert adapter.get("key2") is None
        assert adapter.get("key3") is not None


class TestAsyncMemoryAdapter:
    """Tests for async AsyncMemoryAdapter."""

    async def test_get_nonexistent_returns_none(
        self, async_adapter: AsyncMemoryAdapter
    ) -> None:
        """Test that getting a nonexistent key returns None."""
        assert await async_adapter.get("nonexistent") is None

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

    async def test_tag_invalidation_time(
        self, async_adapter: AsyncMemoryAdapter
    ) -> None:
        """Test setting and getting tag invalidation time."""
        tag = Tag(("user", "123"))
        assert await async_adapter.get_tag_invalidation_time(tag) is None

        await async_adapter.set_tag_invalidation_time(tag, 1000)
        assert await async_adapter.get_tag_invalidation_time(tag) == 1000

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
