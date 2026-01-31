"""Tests for primitives API."""

import asyncio

import pytest

from t87s import AsyncMemoryAdapter
from t87s.primitives import create_primitives


@pytest.fixture
def primitives():
    adapter = AsyncMemoryAdapter()
    return create_primitives(adapter=adapter, default_ttl="10s")


class TestQuery:
    """Tests for query() with stampede protection."""

    async def test_cache_miss_calls_fn(self, primitives) -> None:
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"id": "123"}

        result = await primitives.query(
            key="user:123",
            tags=[("users", "123")],
            fn=fetch,
        )
        assert result == {"id": "123"}
        assert fetch_count == 1

    async def test_cache_hit_returns_cached(self, primitives) -> None:
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"id": "123"}

        await primitives.query(key="user:123", tags=[("users", "123")], fn=fetch)
        await primitives.query(key="user:123", tags=[("users", "123")], fn=fetch)
        assert fetch_count == 1

    async def test_stampede_protection(self, primitives) -> None:
        """Concurrent requests share the same fetch."""
        fetch_count = 0
        fetch_started = asyncio.Event()

        async def slow_fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            fetch_started.set()
            await asyncio.sleep(0.1)
            return {"id": "123"}

        # Launch concurrent requests
        tasks = [
            asyncio.create_task(
                primitives.query(key="user:123", tags=[("users", "123")], fn=slow_fetch)
            )
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)
        assert all(r == {"id": "123"} for r in results)
        assert fetch_count == 1  # Only one fetch despite 5 requests


class TestGetSetDel:
    """Tests for escape hatch operations."""

    async def test_get_returns_none_for_missing(self, primitives) -> None:
        result = await primitives.get("nonexistent")
        assert result is None

    async def test_set_and_get(self, primitives) -> None:
        await primitives.set(
            "manual:key",
            {"data": "value"},
            tags=[("manual",)],
            ttl="1h",
        )
        result = await primitives.get("manual:key")
        assert result == {"data": "value"}

    async def test_del_removes_entry(self, primitives) -> None:
        await primitives.set("key", "value", tags=[], ttl="1h")
        await primitives.delete("key")
        result = await primitives.get("key")
        assert result is None


class TestInvalidate:
    """Tests for tag-based invalidation."""

    async def test_invalidate_makes_entry_stale(self, primitives) -> None:
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        await primitives.query(key="user:123", tags=[("users", "123")], fn=fetch)
        assert fetch_count == 1

        await primitives.invalidate([("users", "123")])

        await primitives.query(key="user:123", tags=[("users", "123")], fn=fetch)
        assert fetch_count == 2

    async def test_hierarchical_invalidation(self, primitives) -> None:
        """Invalidating parent invalidates children."""
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        await primitives.query(
            key="post:1:comment:1",
            tags=[("posts", "1", "comments", "1")],
            fn=fetch,
        )
        assert fetch_count == 1

        # Invalidate parent tag
        await primitives.invalidate([("posts", "1")])

        await primitives.query(
            key="post:1:comment:1",
            tags=[("posts", "1", "comments", "1")],
            fn=fetch,
        )
        assert fetch_count == 2


class TestTTLAndGrace:
    """Tests for TTL expiration and grace period."""

    async def test_expired_entry_refetches(self) -> None:
        adapter = AsyncMemoryAdapter()
        p = create_primitives(adapter=adapter, default_ttl="1ms")
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        await p.query(key="key", tags=[], fn=fetch, ttl="1ms")
        assert fetch_count == 1

        await asyncio.sleep(0.01)

        await p.query(key="key", tags=[], fn=fetch, ttl="1ms")
        assert fetch_count == 2

    async def test_grace_period_returns_stale(self) -> None:
        adapter = AsyncMemoryAdapter()
        p = create_primitives(adapter=adapter, default_ttl="1ms", default_grace="1s")
        fetch_count = 0

        async def fetch() -> dict:
            nonlocal fetch_count
            fetch_count += 1
            return {"count": fetch_count}

        result1 = await p.query(key="key", tags=[], fn=fetch, ttl="1ms", grace="1s")
        assert result1["count"] == 1

        await asyncio.sleep(0.01)  # Expire TTL but within grace

        # Should return stale value immediately
        result2 = await p.query(key="key", tags=[], fn=fetch, ttl="1ms", grace="1s")
        assert result2["count"] == 1  # Stale value

        # Wait for background refresh
        await asyncio.sleep(0.1)

        result3 = await p.query(key="key", tags=[], fn=fetch, ttl="1ms", grace="1s")
        assert result3["count"] == 2


class TestClearAndDisconnect:
    """Tests for clear and disconnect."""

    async def test_clear_removes_all(self, primitives) -> None:
        await primitives.set("key1", "val1", tags=[], ttl="1h")
        await primitives.set("key2", "val2", tags=[], ttl="1h")

        await primitives.clear()

        assert await primitives.get("key1") is None
        assert await primitives.get("key2") is None

    async def test_disconnect(self, primitives) -> None:
        await primitives.disconnect()
        # Should not raise
