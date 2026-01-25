"""Tests for async cache client."""

import asyncio

import pytest

from t87s import (
    AsyncMemoryAdapter,
    AsyncQueryConfig,
    AsyncT87s,
    MutationResult,
    define_tags,
)


@pytest.fixture
def async_t87s_client(async_adapter: AsyncMemoryAdapter) -> AsyncT87s:
    """Create an AsyncT87s client with an async memory adapter."""
    return AsyncT87s(async_adapter, default_ttl="10s")


@pytest.fixture
def tags() -> dict:
    """Create tag definitions for tests."""
    return define_tags(
        {
            "user": lambda id: ("user", id),
            "post": lambda id: ("post", id),
            "user_posts": lambda user_id: ("user", user_id, "posts"),
        }
    )


class TestAsyncCacheMissAndHit:
    """Tests for basic async cache miss and hit behavior."""

    async def test_cache_miss_calls_fn(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that cache miss calls the fetch function."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        result = await get_user("123")
        assert result == {"id": "123"}
        assert fetch_count == 1

    async def test_cache_hit_returns_cached(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that cache hit returns cached value without calling fn."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        await get_user("123")
        await get_user("123")
        assert fetch_count == 1

    async def test_different_keys_are_separate(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that different keys have separate cache entries."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        await get_user("123")
        await get_user("456")
        assert fetch_count == 2


class TestAsyncInvalidation:
    """Tests for async cache invalidation."""

    async def test_mutation_invalidates(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that mutation decorator invalidates tags."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        @async_t87s_client.mutation
        async def update_user(id: str) -> MutationResult[dict]:
            return MutationResult(
                result={"id": id, "updated": True}, invalidates=[tags["user"](id)]
            )

        await get_user("123")
        assert fetch_count == 1

        await update_user("123")
        await get_user("123")
        assert fetch_count == 2

    async def test_manual_invalidation(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test manual invalidation."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        await get_user("123")
        assert fetch_count == 1

        await async_t87s_client.invalidate([tags["user"]("123")])
        await get_user("123")
        assert fetch_count == 2

    async def test_prefix_invalidation(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that invalidating a prefix invalidates all children."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        await get_user("A")
        await get_user("B")
        assert fetch_count == 2

        await async_t87s_client.invalidate([("user",)])  # Invalidate all users
        await get_user("A")
        await get_user("B")
        assert fetch_count == 4


class TestAsyncClear:
    """Tests for clearing the async cache."""

    async def test_clear_removes_all_entries(
        self, async_t87s_client: AsyncT87s, tags: dict
    ) -> None:
        """Test that clear removes all cached entries."""
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        await get_user("123")
        await get_user("456")
        assert fetch_count == 2

        await async_t87s_client.clear()
        await get_user("123")
        await get_user("456")
        assert fetch_count == 4


class TestAsyncTTLExpiration:
    """Tests for TTL expiration in async client."""

    async def test_expired_entry_refetches(
        self, async_adapter: AsyncMemoryAdapter, tags: dict
    ) -> None:
        """Test that expired entries are refetched."""
        async_t87s_client = AsyncT87s(async_adapter, default_ttl="1ms")
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return AsyncQueryConfig(tags=[tags["user"](id)], ttl="1ms", fn=fetch)

        await get_user("123")
        assert fetch_count == 1

        await asyncio.sleep(0.01)  # Wait for TTL to expire
        await get_user("123")
        assert fetch_count == 2


class TestAsyncGracePeriod:
    """Tests for grace period behavior in async client."""

    async def test_within_grace_returns_stale(
        self, async_adapter: AsyncMemoryAdapter, tags: dict
    ) -> None:
        """Test that stale entries within grace period return stale value."""
        async_t87s_client = AsyncT87s(
            async_adapter, default_ttl="1ms", default_grace="1s"
        )
        fetch_count = 0

        @async_t87s_client.query
        def get_user(id: str) -> AsyncQueryConfig[dict]:
            async def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id, "version": fetch_count}

            return AsyncQueryConfig(
                tags=[tags["user"](id)], ttl="1ms", grace="1s", fn=fetch
            )

        result1 = await get_user("123")
        assert result1["version"] == 1
        assert fetch_count == 1

        await asyncio.sleep(0.01)  # Wait for TTL to expire but within grace

        # Should return stale value immediately
        result2 = await get_user("123")
        assert result2["version"] == 1  # Still stale value

        # Wait for background refresh
        await asyncio.sleep(0.1)

        # Now should have fresh value
        result3 = await get_user("123")
        assert result3["version"] == 2
