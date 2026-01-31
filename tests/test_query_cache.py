"""Tests for QueryCache with @cached decorator."""

from dataclasses import dataclass
from typing import Any

import pytest

from t87s import AsyncMemoryAdapter
from t87s.query_cache import QueryCache, cached
from t87s.schema import Static, TagSchema, Wild


# Test schema
class CommentChildren(TagSchema):
    pass


class PostChildren(TagSchema):
    comments: Wild[CommentChildren]
    settings: Static


class TestTags(TagSchema):
    posts: Wild[PostChildren]
    users: Wild[TagSchema]
    config: Static


@dataclass
class User:
    id: str
    name: str


@dataclass
class Post:
    id: str
    title: str


class TestQueryCacheBasics:
    """Basic QueryCache functionality."""

    async def test_cached_method_returns_value(self) -> None:
        class MyCache(QueryCache[TestTags]):
            @cached(TestTags.users())
            async def get_user(self, id: str) -> User:
                return User(id=id, name=f"User {id}")

        cache = MyCache(adapter=AsyncMemoryAdapter())
        user = await cache.get_user("123")
        assert user.id == "123"
        assert user.name == "User 123"

    async def test_cached_method_caches(self) -> None:
        fetch_count = 0

        class MyCache(QueryCache[TestTags]):
            @cached(TestTags.users())
            async def get_user(self, id: str) -> User:
                nonlocal fetch_count
                fetch_count += 1
                return User(id=id, name=f"User {id}")

        cache = MyCache(adapter=AsyncMemoryAdapter())
        await cache.get_user("123")
        await cache.get_user("123")
        assert fetch_count == 1

    async def test_wild_count_validation(self) -> None:
        """Methods must have same param count as wilds."""
        with pytest.raises(TypeError, match="wilds"):

            class BadCache(QueryCache[TestTags]):
                @cached(TestTags.users())  # 1 wild
                async def get_user(self) -> User:  # 0 params
                    return User("", "")


class TestQueryCacheTags:
    """Test tag construction and invalidation."""

    async def test_t_property_returns_instance(self) -> None:
        class MyCache(QueryCache[TestTags]):
            pass

        cache = MyCache(adapter=AsyncMemoryAdapter())
        assert isinstance(cache.t, TestTags)

    async def test_invalidate_with_typed_tag(self) -> None:
        fetch_count = 0

        class MyCache(QueryCache[TestTags]):
            @cached(TestTags.users())
            async def get_user(self, id: str) -> User:
                nonlocal fetch_count
                fetch_count += 1
                return User(id=id, name=f"User {id}")

        cache = MyCache(adapter=AsyncMemoryAdapter())
        await cache.get_user("123")
        assert fetch_count == 1

        await cache.invalidate(cache.t.users("123"))
        await cache.get_user("123")
        assert fetch_count == 2

    async def test_hierarchical_invalidation(self) -> None:
        post_fetch_count = 0
        comment_fetch_count = 0

        class MyCache(QueryCache[TestTags]):
            @cached(TestTags.posts())
            async def get_post(self, id: str) -> Post:
                nonlocal post_fetch_count
                post_fetch_count += 1
                return Post(id=id, title=f"Post {id}")

            @cached(TestTags.posts().comments())
            async def get_comment(self, post_id: str, comment_id: str) -> dict:
                nonlocal comment_fetch_count
                comment_fetch_count += 1
                return {"post": post_id, "comment": comment_id}

        cache = MyCache(adapter=AsyncMemoryAdapter())
        await cache.get_post("p1")
        await cache.get_comment("p1", "c1")
        assert post_fetch_count == 1
        assert comment_fetch_count == 1

        # Invalidate parent - should invalidate both
        await cache.invalidate(cache.t.posts("p1"))

        await cache.get_post("p1")
        await cache.get_comment("p1", "c1")
        assert post_fetch_count == 2
        assert comment_fetch_count == 2


class TestQueryCachePrimitives:
    """Test primitives escape hatch."""

    async def test_primitives_property(self) -> None:
        class MyCache(QueryCache[TestTags]):
            pass

        cache = MyCache(adapter=AsyncMemoryAdapter())
        assert cache.primitives is not None

    async def test_primitives_set_and_get(self) -> None:
        class MyCache(QueryCache[TestTags]):
            pass

        cache = MyCache(adapter=AsyncMemoryAdapter())
        await cache.primitives.set("manual", "value", tags=[], ttl="1h")
        result = await cache.primitives.get("manual")
        assert result == "value"


class TestStaticTags:
    """Test static (leaf) tags."""

    async def test_static_tag_no_params(self) -> None:
        fetch_count = 0

        class MyCache(QueryCache[TestTags]):
            @cached(TestTags.config)
            async def get_config(self) -> dict[str, Any]:
                nonlocal fetch_count
                fetch_count += 1
                return {"theme": "dark"}

        cache = MyCache(adapter=AsyncMemoryAdapter())
        config = await cache.get_config()
        assert config["theme"] == "dark"
        assert fetch_count == 1

        await cache.get_config()
        assert fetch_count == 1  # Cached
