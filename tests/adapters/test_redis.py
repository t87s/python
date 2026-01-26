"""Integration tests for Redis adapters using testcontainers."""

import pytest

# Skip all tests if redis or testcontainers are not installed
pytest.importorskip("redis")
pytest.importorskip("testcontainers")

import asyncio

import redis
import redis.asyncio
from testcontainers.redis import RedisContainer

from t87s import CacheEntry, Tag
from t87s.adapters.redis import AsyncRedisAdapter, RedisAdapter


@pytest.fixture(scope="module")
def redis_container():
    """Start a Redis container for the test module."""
    with RedisContainer() as container:
        yield container


@pytest.fixture
def redis_client(redis_container):
    """Create a sync Redis client."""
    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        decode_responses=False,
    )
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def async_redis_client(redis_container):
    """Create an async Redis client."""
    client = redis.asyncio.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        decode_responses=False,
    )
    yield client
    # Cleanup handled in test


@pytest.fixture
def redis_adapter(redis_client) -> RedisAdapter:
    """Create a RedisAdapter with a test prefix."""
    return RedisAdapter(redis_client, prefix="test")


@pytest.fixture
def async_redis_adapter(async_redis_client) -> AsyncRedisAdapter:
    """Create an AsyncRedisAdapter with a test prefix."""
    return AsyncRedisAdapter(async_redis_client, prefix="test")


class TestRedisAdapter:
    """Integration tests for sync RedisAdapter."""

    def test_get_nonexistent_returns_none(self, redis_adapter: RedisAdapter) -> None:
        """Test that getting a nonexistent key returns None."""
        assert redis_adapter.get("nonexistent") is None

    def test_set_and_get(self, redis_adapter: RedisAdapter) -> None:
        """Test setting and getting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value={"id": "123", "name": "Test"},
            tags=[Tag(("user", "123"))],
            created_at=1000,
            expires_at=9999999999999,  # Far future
            grace_until=None,
        )
        redis_adapter.set("key1", entry)
        result = redis_adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "123", "name": "Test"}
        assert result.tags == [("user", "123")]
        assert result.created_at == 1000

    def test_delete(self, redis_adapter: RedisAdapter) -> None:
        """Test deleting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=9999999999999,
            grace_until=None,
        )
        redis_adapter.set("key1", entry)
        redis_adapter.delete("key1")
        assert redis_adapter.get("key1") is None

    def test_tag_invalidation_time(self, redis_adapter: RedisAdapter) -> None:
        """Test setting and getting tag invalidation time."""
        tag = Tag(("user", "123"))
        assert redis_adapter.get_tag_invalidation_time(tag) is None

        redis_adapter.set_tag_invalidation_time(tag, 1000)
        assert redis_adapter.get_tag_invalidation_time(tag) == 1000

    def test_clear(self, redis_adapter: RedisAdapter) -> None:
        """Test clearing all cached entries."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=9999999999999,
            grace_until=None,
        )
        redis_adapter.set("key1", entry)
        redis_adapter.set("key2", entry)

        # Also set a tag invalidation time
        redis_adapter.set_tag_invalidation_time(Tag(("user",)), 1000)

        redis_adapter.clear()

        # Cache entries should be cleared
        assert redis_adapter.get("key1") is None
        assert redis_adapter.get("key2") is None

        # Tag invalidation times should remain
        assert redis_adapter.get_tag_invalidation_time(Tag(("user",))) == 1000

    def test_ttl_expiration(self, redis_adapter: RedisAdapter) -> None:
        """Test that entries expire based on TTL."""
        import time

        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=int(time.time() * 1000) + 100,  # 100ms from now
            grace_until=None,
        )
        redis_adapter.set("expiring_key", entry)

        # Should exist immediately
        assert redis_adapter.get("expiring_key") is not None

        # Wait for expiration
        time.sleep(0.2)

        # Should be gone
        assert redis_adapter.get("expiring_key") is None


class TestAsyncRedisAdapter:
    """Integration tests for async AsyncRedisAdapter."""

    async def test_get_nonexistent_returns_none(
        self, async_redis_adapter: AsyncRedisAdapter
    ) -> None:
        """Test that getting a nonexistent key returns None."""
        assert await async_redis_adapter.get("nonexistent") is None

    async def test_set_and_get(self, async_redis_adapter: AsyncRedisAdapter) -> None:
        """Test setting and getting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value={"id": "456", "name": "Async Test"},
            tags=[Tag(("post", "456"))],
            created_at=2000,
            expires_at=9999999999999,
            grace_until=None,
        )
        await async_redis_adapter.set("async_key1", entry)
        result = await async_redis_adapter.get("async_key1")
        assert result is not None
        assert result.value == {"id": "456", "name": "Async Test"}
        assert result.tags == [("post", "456")]

    async def test_delete(self, async_redis_adapter: AsyncRedisAdapter) -> None:
        """Test deleting a value."""
        entry: CacheEntry[object] = CacheEntry(
            value="async_test",
            tags=[],
            created_at=1000,
            expires_at=9999999999999,
            grace_until=None,
        )
        await async_redis_adapter.set("async_key1", entry)
        await async_redis_adapter.delete("async_key1")
        assert await async_redis_adapter.get("async_key1") is None

    async def test_tag_invalidation_time(
        self, async_redis_adapter: AsyncRedisAdapter
    ) -> None:
        """Test setting and getting tag invalidation time."""
        tag = Tag(("post", "456"))
        assert await async_redis_adapter.get_tag_invalidation_time(tag) is None

        await async_redis_adapter.set_tag_invalidation_time(tag, 2000)
        assert await async_redis_adapter.get_tag_invalidation_time(tag) == 2000

    async def test_clear(self, async_redis_adapter: AsyncRedisAdapter) -> None:
        """Test clearing all cached entries."""
        entry: CacheEntry[object] = CacheEntry(
            value="test",
            tags=[],
            created_at=1000,
            expires_at=9999999999999,
            grace_until=None,
        )
        await async_redis_adapter.set("async_key1", entry)
        await async_redis_adapter.set("async_key2", entry)

        await async_redis_adapter.clear()

        assert await async_redis_adapter.get("async_key1") is None
        assert await async_redis_adapter.get("async_key2") is None

    async def test_ttl_expiration(self, async_redis_adapter: AsyncRedisAdapter) -> None:
        """Test that entries expire based on TTL."""
        import time

        entry: CacheEntry[object] = CacheEntry(
            value="async_expiring",
            tags=[],
            created_at=1000,
            expires_at=int(time.time() * 1000) + 100,  # 100ms from now
            grace_until=None,
        )
        await async_redis_adapter.set("async_expiring_key", entry)

        # Should exist immediately
        assert await async_redis_adapter.get("async_expiring_key") is not None

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Should be gone
        assert await async_redis_adapter.get("async_expiring_key") is None
