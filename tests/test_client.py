"""Tests for sync cache client."""

import time

import pytest

from t87s import MemoryAdapter, MutationResult, QueryConfig, T87s, define_tags


@pytest.fixture
def t87s_client(adapter: MemoryAdapter) -> T87s:
    """Create a T87s client with a memory adapter."""
    return T87s(adapter, default_ttl="10s")


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


class TestCacheMissAndHit:
    """Tests for basic cache miss and hit behavior."""

    def test_cache_miss_calls_fn(self, t87s_client: T87s, tags: dict) -> None:
        """Test that cache miss calls the fetch function."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        result = get_user("123")
        assert result == {"id": "123"}
        assert fetch_count == 1

    def test_cache_hit_returns_cached(self, t87s_client: T87s, tags: dict) -> None:
        """Test that cache hit returns cached value without calling fn."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        get_user("123")
        get_user("123")
        assert fetch_count == 1

    def test_different_keys_are_separate(self, t87s_client: T87s, tags: dict) -> None:
        """Test that different keys have separate cache entries."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        get_user("123")
        get_user("456")
        assert fetch_count == 2


class TestInvalidation:
    """Tests for cache invalidation."""

    def test_mutation_invalidates(self, t87s_client: T87s, tags: dict) -> None:
        """Test that mutation decorator invalidates tags."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        @t87s_client.mutation
        def update_user(id: str) -> MutationResult[dict]:
            return MutationResult(
                result={"id": id, "updated": True}, invalidates=[tags["user"](id)]
            )

        get_user("123")
        assert fetch_count == 1

        update_user("123")
        get_user("123")
        assert fetch_count == 2

    def test_manual_invalidation(self, t87s_client: T87s, tags: dict) -> None:
        """Test manual invalidation."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        get_user("123")
        assert fetch_count == 1

        t87s_client.invalidate([tags["user"]("123")])
        get_user("123")
        assert fetch_count == 2

    def test_prefix_invalidation(self, t87s_client: T87s, tags: dict) -> None:
        """Test that invalidating a prefix invalidates all children."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        get_user("A")
        get_user("B")
        assert fetch_count == 2

        t87s_client.invalidate([("user",)])  # Invalidate all users
        get_user("A")
        get_user("B")
        assert fetch_count == 4

    def test_invalidation_isolation(self, t87s_client: T87s, tags: dict) -> None:
        """Test that invalidation doesn't affect unrelated entries."""
        user_fetch_count = 0
        post_fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal user_fetch_count
                user_fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        @t87s_client.query
        def get_post(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal post_fetch_count
                post_fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["post"](id)], ttl="10s", fn=fetch)

        get_user("123")
        get_post("456")
        assert user_fetch_count == 1
        assert post_fetch_count == 1

        t87s_client.invalidate([tags["user"]("123")])
        get_user("123")
        get_post("456")
        assert user_fetch_count == 2
        assert post_fetch_count == 1  # Post should not be affected


class TestClear:
    """Tests for clearing the cache."""

    def test_clear_removes_all_entries(self, t87s_client: T87s, tags: dict) -> None:
        """Test that clear removes all cached entries."""
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="10s", fn=fetch)

        get_user("123")
        get_user("456")
        assert fetch_count == 2

        t87s_client.clear()
        get_user("123")
        get_user("456")
        assert fetch_count == 4


class TestTTLExpiration:
    """Tests for TTL expiration."""

    def test_expired_entry_refetches(self, adapter: MemoryAdapter, tags: dict) -> None:
        """Test that expired entries are refetched."""
        t87s_client = T87s(adapter, default_ttl="1ms")
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id}

            return QueryConfig(tags=[tags["user"](id)], ttl="1ms", fn=fetch)

        get_user("123")
        assert fetch_count == 1

        time.sleep(0.01)  # Wait for TTL to expire
        get_user("123")
        assert fetch_count == 2


class TestGracePeriod:
    """Tests for grace period behavior."""

    def test_within_grace_returns_stale(
        self, adapter: MemoryAdapter, tags: dict
    ) -> None:
        """Test that stale entries within grace period return stale value."""
        t87s_client = T87s(adapter, default_ttl="1ms", default_grace="1s")
        fetch_count = 0

        @t87s_client.query
        def get_user(id: str) -> QueryConfig[dict]:
            def fetch() -> dict:
                nonlocal fetch_count
                fetch_count += 1
                return {"id": id, "version": fetch_count}

            return QueryConfig(tags=[tags["user"](id)], ttl="1ms", grace="1s", fn=fetch)

        result1 = get_user("123")
        assert result1["version"] == 1
        assert fetch_count == 1

        time.sleep(0.01)  # Wait for TTL to expire but within grace

        # Should return stale value immediately
        result2 = get_user("123")
        assert result2["version"] == 1  # Still stale value

        # Wait for background refresh
        time.sleep(0.1)

        # Now should have fresh value
        result3 = get_user("123")
        assert result3["version"] == 2
