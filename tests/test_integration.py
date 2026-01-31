"""Integration tests for the complete QueryCache flow."""

import asyncio

import pytest

from t87s import AsyncMemoryAdapter, QueryCache, Static, TagSchema, Wild, cached


class CommentChildren(TagSchema):
    pass


class PostChildren(TagSchema):
    comments: Wild[CommentChildren]
    metadata: Static


class BlogTags(TagSchema):
    posts: Wild[PostChildren]
    users: Wild[TagSchema]
    site: Static


class TestBlogCache(QueryCache[BlogTags]):
    """Blog cache for integration testing."""

    def __init__(self, adapter: AsyncMemoryAdapter) -> None:
        super().__init__(adapter=adapter, default_ttl="5s")
        self._db = {
            "posts": {
                "p1": {"title": "First Post", "author": "alice"},
                "p2": {"title": "Second Post", "author": "bob"},
            },
            "users": {
                "alice": {"name": "Alice", "email": "alice@test.com"},
                "bob": {"name": "Bob", "email": "bob@test.com"},
            },
            "comments": {
                ("p1", "c1"): {"body": "Great post!", "author": "bob"},
                ("p1", "c2"): {"body": "Thanks!", "author": "alice"},
            },
        }
        self._fetch_count = 0

    @cached(BlogTags.posts())
    async def get_post(self, post_id: str) -> dict[str, str]:
        self._fetch_count += 1
        await asyncio.sleep(0.01)  # Simulate network
        return self._db["posts"][post_id]

    @cached(BlogTags.users())
    async def get_user(self, user_id: str) -> dict[str, str]:
        self._fetch_count += 1
        await asyncio.sleep(0.01)
        return self._db["users"][user_id]

    @cached(BlogTags.posts().comments())
    async def get_comment(self, post_id: str, comment_id: str) -> dict[str, str]:
        self._fetch_count += 1
        await asyncio.sleep(0.01)
        return self._db["comments"][(post_id, comment_id)]


class TestCachingFlow:
    """Test basic caching behavior."""

    @pytest.mark.asyncio
    async def test_first_call_fetches_from_source(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        post = await cache.get_post("p1")

        assert post["title"] == "First Post"
        assert cache._fetch_count == 1

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.get_post("p1")
        await cache.get_post("p1")

        assert cache._fetch_count == 1  # Only one fetch

    @pytest.mark.asyncio
    async def test_different_ids_fetch_separately(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.get_post("p1")
        await cache.get_post("p2")

        assert cache._fetch_count == 2


class TestInvalidationFlow:
    """Test invalidation behavior."""

    @pytest.mark.asyncio
    async def test_invalidate_single_entry(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.get_post("p1")
        await cache.get_post("p2")
        assert cache._fetch_count == 2

        # Invalidate only p1
        await cache.invalidate(cache.t.posts("p1"))

        await cache.get_post("p1")  # Should refetch
        await cache.get_post("p2")  # Should use cache
        assert cache._fetch_count == 3

    @pytest.mark.asyncio
    async def test_invalidate_parent_affects_children(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.get_comment("p1", "c1")
        await cache.get_comment("p1", "c2")
        assert cache._fetch_count == 2

        # Invalidate all of p1's comments by invalidating the parent
        await cache.invalidate(cache.t.posts("p1"))

        await cache.get_comment("p1", "c1")  # Should refetch
        await cache.get_comment("p1", "c2")  # Should refetch
        assert cache._fetch_count == 4

    @pytest.mark.asyncio
    async def test_invalidate_root_clears_all(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.get_post("p1")
        await cache.get_user("alice")
        await cache.get_comment("p1", "c1")
        assert cache._fetch_count == 3

        # Invalidate at root level (posts)
        await cache.invalidate(cache.t.posts)

        await cache.get_post("p1")  # Should refetch
        await cache.get_comment("p1", "c1")  # Should refetch (under posts)
        await cache.get_user("alice")  # Should still be cached (not under posts)
        assert cache._fetch_count == 5


class TestStampedeProtection:
    """Test that concurrent requests are coalesced."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_coalesced(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        # Fire 10 concurrent requests for same post
        tasks = [cache.get_post("p1") for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should get same result
        assert all(r["title"] == "First Post" for r in results)
        # But only one fetch should have happened
        assert cache._fetch_count == 1

    @pytest.mark.asyncio
    async def test_different_keys_not_coalesced(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        # Fire concurrent requests for different posts
        tasks = [cache.get_post("p1"), cache.get_post("p2")]
        await asyncio.gather(*tasks)

        # Should have separate fetches
        assert cache._fetch_count == 2


class TestSchemaTyping:
    """Test that the schema provides correct typing at runtime."""

    def test_class_access_gives_specs(self) -> None:
        spec = BlogTags.posts()
        assert spec.segments == ("posts", "*")
        assert spec.wild_count == 1

    def test_instance_access_gives_paths(self) -> None:
        tags = BlogTags()
        path = tags.posts("p1").path
        assert path == ("posts", "p1")

    def test_nested_paths(self) -> None:
        tags = BlogTags()
        path = tags.posts("p1").comments("c1").path
        assert path == ("posts", "p1", "comments", "c1")

    def test_static_segments(self) -> None:
        tags = BlogTags()
        path = tags.site.path
        assert path == ("site",)


class TestPrimitivesEscapeHatch:
    """Test that primitives escape hatch works."""

    @pytest.mark.asyncio
    async def test_direct_get_set(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.primitives.set(
            "manual:key", {"data": "value"}, tags=[("manual",)], ttl="1h"
        )
        result = await cache.primitives.get("manual:key")

        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_direct_delete(self) -> None:
        adapter = AsyncMemoryAdapter()
        cache = TestBlogCache(adapter)

        await cache.primitives.set(
            "manual:key", {"data": "value"}, tags=[("manual",)], ttl="1h"
        )
        await cache.primitives.delete("manual:key")
        result = await cache.primitives.get("manual:key")

        assert result is None
