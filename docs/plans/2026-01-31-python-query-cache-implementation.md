# Python QueryCache Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Python QueryCache with class-based TagSchema and `@cached` decorator, matching TS behavior with Pythonic syntax.

**Architecture:** Extract spike32 patterns (TagSchema, Wild[T], QueryCache) into production modules. Add `create_primitives()` wrapper. Existing adapters/types work as-is.

**Tech Stack:** Python 3.10+, mypy strict, pytest-asyncio, ruff

---

## What Already Exists

The Python package already has substantial code:

| Module | Status | Notes |
|--------|--------|-------|
| `types.py` | ✅ Complete | CacheEntry, QueryConfig, Tag, Duration |
| `duration.py` | ✅ Complete | parse_duration() |
| `adapters/base.py` | ✅ Complete | StorageAdapter, AsyncStorageAdapter, VerifiableAdapter protocols |
| `adapters/memory.py` | ✅ Complete | MemoryAdapter, AsyncMemoryAdapter with LRU |
| `client.py` | ✅ Complete | T87s sync client (OLD API) |
| `async_client.py` | ✅ Complete | AsyncT87s async client (OLD API) |
| `tags.py` | ✅ Complete | define_tags, serialize_tag, deserialize_tag |
| `tests/` | ✅ 88 tests | Tests for existing functionality |

## What We're Adding

| Module | Status | Notes |
|--------|--------|-------|
| `primitives.py` | 🆕 New | `create_primitives()`, Primitives class |
| `schema.py` | 🆕 New | TagSchema, Wild[T], Static, TypedTag |
| `query_cache.py` | 🆕 New | QueryCache[T], @cached decorator |
| `__init__.py` | 📝 Update | Add new exports |
| `tests/test_primitives.py` | 🆕 New | Primitives tests |
| `tests/test_schema.py` | 🆕 New | Schema type tests |
| `tests/test_query_cache.py` | 🆕 New | QueryCache integration tests |

---

## Task 1: Create TypedTag Dataclass

**Files:**
- Create: `src/t87s/typed_tag.py`
- Test: `tests/test_typed_tag.py`

**Step 1: Write the failing test**

```python
# tests/test_typed_tag.py
"""Tests for TypedTag."""

from t87s.typed_tag import TypedTag


class TestTypedTag:
    def test_create_from_tuple(self) -> None:
        tag = TypedTag(("users", "123"))
        assert tag.path == ("users", "123")

    def test_repr(self) -> None:
        tag = TypedTag(("users", "123", "posts"))
        assert repr(tag) == "Tag(users/123/posts)"

    def test_frozen(self) -> None:
        tag = TypedTag(("users",))
        # Should raise FrozenInstanceError
        import pytest
        with pytest.raises(Exception):
            tag.path = ("other",)  # type: ignore

    def test_hashable(self) -> None:
        tag1 = TypedTag(("users", "123"))
        tag2 = TypedTag(("users", "123"))
        assert hash(tag1) == hash(tag2)
        assert {tag1, tag2} == {tag1}
```

**Step 2: Run test to verify it fails**

Run: `cd /home/mikesol/Documents/GitHub/t87s/t87s/.worktrees/maximalist-types-spike/packages/python && source .venv/bin/activate && pytest tests/test_typed_tag.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/t87s/typed_tag.py
"""TypedTag for type-safe cache invalidation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TypedTag:
    """A type-safe tag for cache invalidation."""
    path: tuple[str, ...]

    def __repr__(self) -> str:
        return f"Tag({'/'.join(self.path)})"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_typed_tag.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_typed_tag.py src/t87s/typed_tag.py
git commit -m "feat(python): add TypedTag dataclass for type-safe invalidation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create Schema System (TagSchema, Wild, Static)

**Files:**
- Create: `src/t87s/schema.py`
- Test: `tests/test_schema.py`

**Step 1: Write the failing tests**

```python
# tests/test_schema.py
"""Tests for TagSchema, Wild, Static system."""

from typing import TYPE_CHECKING

import pytest

from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag


class ChildTags(TagSchema):
    pass


class PostChildren(TagSchema):
    comments: Wild[ChildTags]
    settings: Static


class RootTags(TagSchema):
    posts: Wild[PostChildren]
    users: Wild[TagSchema]
    config: Static


class TestSchemaClassAccess:
    """Test class-level access (for @cached decorator specs)."""

    def test_wild_returns_spec(self) -> None:
        spec = RootTags.posts
        assert spec.segments == ("posts",)
        assert spec.wild_count == 0

    def test_wild_call_adds_wild(self) -> None:
        spec = RootTags.posts()
        assert spec.segments == ("posts", "*")
        assert spec.wild_count == 1

    def test_chained_access(self) -> None:
        spec = RootTags.posts().comments
        assert spec.segments == ("posts", "*", "comments")
        assert spec.wild_count == 1

    def test_chained_with_multiple_wilds(self) -> None:
        spec = RootTags.posts().comments()
        assert spec.segments == ("posts", "*", "comments", "*")
        assert spec.wild_count == 2

    def test_static_access(self) -> None:
        spec = RootTags.config
        assert spec.segments == ("config",)
        assert spec.wild_count == 0


class TestSchemaInstanceAccess:
    """Test instance-level access (for runtime tag construction)."""

    def test_wild_returns_node(self) -> None:
        root = RootTags()
        node = root.posts
        assert node.path == ("posts",)

    def test_wild_call_builds_tag_path(self) -> None:
        root = RootTags()
        child = root.posts("123")
        assert child.path == ("posts", "123")

    def test_chained_instance_access(self) -> None:
        root = RootTags()
        child = root.posts("p1").comments("c1")
        assert child.path == ("posts", "p1", "comments", "c1")

    def test_static_returns_typed_tag(self) -> None:
        root = RootTags()
        tag = root.config
        assert isinstance(tag, TypedTag)
        assert tag.path == ("config",)


class TestBuildPath:
    """Test building paths from specs."""

    def test_build_path_single_wild(self) -> None:
        spec = RootTags.posts()
        path = spec.build_path(("123",))
        assert path == ("posts", "123")

    def test_build_path_multiple_wilds(self) -> None:
        spec = RootTags.posts().comments()
        path = spec.build_path(("p1", "c1"))
        assert path == ("posts", "p1", "comments", "c1")

    def test_build_path_no_wilds(self) -> None:
        spec = RootTags.config
        path = spec.build_path(())
        assert path == ("config",)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# src/t87s/schema.py
"""TagSchema system for type-safe cache tags.

This module provides:
- TagSchema: Base class for defining tag schemas
- Wild[T]: Annotation for parameterized (wild) tag segments
- Static: Annotation for leaf (static) tag segments
- Descriptors that enable dual behavior:
  - Class access: Returns specs for @cached decorator
  - Instance access: Returns nodes for runtime tag construction
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from t87s.typed_tag import TypedTag

ChildrenT = TypeVar("ChildrenT", bound="TagSchema")

# =============================================================================
# Tag Spec (runtime) - used by @cached decorator
# =============================================================================


class TagSpec:
    """Represents a tag path pattern with wildcards."""

    __slots__ = ("_segments", "_wild_count", "_children_type")

    def __init__(
        self,
        segments: tuple[str, ...] = (),
        wild_count: int = 0,
        children_type: type[TagSchema] | None = None,
    ) -> None:
        self._segments = segments
        self._wild_count = wild_count
        self._children_type = children_type

    def __call__(self) -> TagSpec:
        """Add a wildcard segment."""
        return TagSpec(
            self._segments + ("*",),
            self._wild_count + 1,
            self._children_type,
        )

    def __getattr__(self, name: str) -> TagSpec:
        if name.startswith("_"):
            raise AttributeError(name)

        children_type = None
        if self._children_type is not None:
            try:
                hints = get_type_hints(self._children_type)
                hint = hints.get(name)
                if hint:
                    origin = get_origin(hint)
                    if origin is not None and origin.__name__ in (
                        "Wild",
                        "_WildMarker",
                    ):
                        args = get_args(hint)
                        if args and isinstance(args[0], type):
                            children_type = args[0]
            except Exception:
                pass

        return TagSpec(
            self._segments + (name,),
            self._wild_count,
            children_type,
        )

    @property
    def wild_count(self) -> int:
        return self._wild_count

    @property
    def segments(self) -> tuple[str, ...]:
        return self._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        """Build a concrete path by filling wildcards with args."""
        result: list[str] = []
        arg_idx = 0
        for seg in self._segments:
            if seg == "*":
                result.append(str(args[arg_idx]))
                arg_idx += 1
            else:
                result.append(seg)
        return tuple(result)

    def __repr__(self) -> str:
        return f"TagSpec({'/'.join(self._segments)}, wilds={self._wild_count})"


# =============================================================================
# WildTagSpec / StaticTagSpec - what mypy sees
# =============================================================================


class WildTagSpec(Generic[ChildrenT]):
    """For mypy: represents a wild tag segment with children type."""

    __slots__ = ("_spec",)

    def __init__(self, spec: TagSpec) -> None:
        self._spec = spec

    if TYPE_CHECKING:

        def __call__(self) -> ChildrenT | WildTagSpec[ChildrenT]: ...
        def __getattr__(self, name: str) -> WildTagSpec[Any]: ...
    else:

        def __call__(self) -> TagSpec:
            return self._spec()

        def __getattr__(self, name: str) -> TagSpec:
            if name.startswith("_"):
                raise AttributeError(name)
            return getattr(self._spec, name)

    @property
    def wild_count(self) -> int:
        return self._spec._wild_count

    @property
    def segments(self) -> tuple[str, ...]:
        return self._spec._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        return self._spec.build_path(args)


class StaticTagSpec:
    """For mypy: represents a static (leaf) tag segment."""

    __slots__ = ("_spec",)

    def __init__(self, spec: TagSpec) -> None:
        self._spec = spec

    @property
    def wild_count(self) -> int:
        return 0

    @property
    def segments(self) -> tuple[str, ...]:
        return self._spec._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        return self._spec.build_path(args)


# =============================================================================
# WildNode - runtime tag construction
# =============================================================================


class WildNode(Generic[ChildrenT]):
    """Runtime node for building typed tags."""

    __slots__ = ("_path", "_children_type")

    def __init__(
        self, path: tuple[str, ...], children_type: type[ChildrenT] | None
    ) -> None:
        self._path = path
        self._children_type = children_type

    @property
    def path(self) -> tuple[str, ...]:
        return self._path

    def __call__(self, id: str) -> ChildrenT:
        """Add a value to the path and return children type."""
        new_path = self._path + (id,)
        if self._children_type is None:
            result = TagSchema.__new__(TagSchema)
            result._path = new_path
            return result  # type: ignore
        result = object.__new__(self._children_type)
        result._path = new_path
        return result


# =============================================================================
# THE KEY: Different Wild for mypy vs runtime
# =============================================================================

if TYPE_CHECKING:
    # For mypy: Wild[T] IS WildTagSpec[T]
    Wild = WildTagSpec
    Static = StaticTagSpec
else:
    # At runtime: Wild is just a marker class for descriptor recognition

    class _WildMarker(Generic[ChildrenT]):
        pass

    Wild = _WildMarker

    class _StaticMarker:
        pass

    Static = _StaticMarker


# =============================================================================
# Descriptors
# =============================================================================


class WildDescriptor(Generic[ChildrenT]):
    """Descriptor for wild tag segments."""

    __slots__ = ("_name", "_children_type")

    def __init__(self, children_type: type[ChildrenT] | None = None) -> None:
        self._name = ""
        self._children_type = children_type

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> WildTagSpec[ChildrenT]: ...

    @overload
    def __get__(self, obj: TagSchema, owner: type) -> WildNode[ChildrenT]: ...

    def __get__(
        self, obj: Any, owner: type
    ) -> WildTagSpec[ChildrenT] | WildNode[ChildrenT]:
        if obj is None:
            # Class access: return spec for @cached
            spec = TagSpec((self._name,), 0, self._children_type)
            return WildTagSpec(spec)
        else:
            # Instance access: return node for tag construction
            return WildNode(obj._path + (self._name,), self._children_type)


class StaticDescriptor:
    """Descriptor for static (leaf) tag segments."""

    __slots__ = ("_name",)

    def __init__(self) -> None:
        self._name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> StaticTagSpec: ...

    @overload
    def __get__(self, obj: TagSchema, owner: type) -> TypedTag: ...

    def __get__(self, obj: Any, owner: type) -> StaticTagSpec | TypedTag:
        if obj is None:
            # Class access: return spec
            spec = TagSpec((self._name,), 0, None)
            return StaticTagSpec(spec)
        else:
            # Instance access: return typed tag
            return TypedTag(obj._path + (self._name,))


# =============================================================================
# TagSchema Base
# =============================================================================


class TagSchema:
    """Base class for defining tag schemas.

    Subclass and add annotations to define your schema:

        class MyTags(TagSchema):
            users: Wild[TagSchema]
            posts: Wild[PostChildren]
            config: Static
    """

    __slots__ = ("_path",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        try:
            hints = get_type_hints(cls)
        except NameError:
            hints = {}

        raw_annotations = getattr(cls, "__annotations__", {})

        for name in set(hints.keys()) | set(raw_annotations.keys()):
            if name.startswith("_") or name in cls.__dict__:
                continue

            hint = hints.get(name)
            raw = raw_annotations.get(name)
            raw_str = str(raw) if raw and not isinstance(raw, str) else (raw or "")

            origin = get_origin(hint) if hint else None
            is_wild = (
                origin is not None
                and getattr(origin, "__name__", "") in ("Wild", "_WildMarker", "WildTagSpec")
            ) or "Wild" in raw_str

            is_static = (
                hint is Static
                or raw_str == "Static"
                or getattr(hint, "__name__", "")
                in ("Static", "_StaticMarker", "StaticTagSpec")
            )

            if is_wild:
                children_type = None
                if origin is not None:
                    args = get_args(hint)
                    if args and isinstance(args[0], type):
                        children_type = args[0]

                desc: WildDescriptor[Any] = WildDescriptor(children_type)
                desc.__set_name__(cls, name)
                setattr(cls, name, desc)

            elif is_static:
                sdesc = StaticDescriptor()
                sdesc.__set_name__(cls, name)
                setattr(cls, name, sdesc)

    def __init__(self, path: tuple[str, ...] = ()) -> None:
        self._path = path

    @property
    def path(self) -> tuple[str, ...]:
        return self._path


__all__ = [
    "TagSchema",
    "Wild",
    "Static",
    "TagSpec",
    "WildTagSpec",
    "StaticTagSpec",
    "TypedTag",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_schema.py -v`
Expected: PASS

**Step 5: Run mypy to verify types**

Run: `mypy src/t87s/schema.py src/t87s/typed_tag.py`
Expected: No errors

**Step 6: Commit**

```bash
git add src/t87s/schema.py tests/test_schema.py
git commit -m "feat(python): add TagSchema, Wild[T], Static schema system

Implements Pythonic equivalent of TS at/wild schema builders:
- TagSchema base class with annotation-based schema definition
- Wild[T] for parameterized tag segments
- Static for leaf tag segments
- Descriptors provide dual behavior for @cached and runtime

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create Async Primitives

**Files:**
- Create: `src/t87s/primitives.py`
- Test: `tests/test_primitives.py`

**Step 1: Write the failing tests**

```python
# tests/test_primitives.py
"""Tests for primitives API."""

import asyncio
import time

import pytest

from t87s import AsyncMemoryAdapter
from t87s.primitives import create_primitives


@pytest.fixture
def primitives() -> ...:
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
                primitives.query(
                    key="user:123", tags=[("users", "123")], fn=slow_fetch
                )
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_primitives.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# src/t87s/primitives.py
"""Primitives API - the axiomatic cache operations.

This module provides low-level cache primitives:
- query(): Cached fetch with stampede protection and SWR
- get(), set(), del(): Raw escape hatches
- invalidate(): Tag-based invalidation
- clear(), disconnect(): Lifecycle methods
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from t87s.adapters.base import AsyncStorageAdapter, AsyncVerifiableAdapter
from t87s.duration import parse_duration
from t87s.types import CacheEntry, Duration, Tag

T = TypeVar("T")


@dataclass
class Primitives:
    """Async cache primitives with stampede protection."""

    _adapter: AsyncStorageAdapter
    _prefix: str
    _default_ttl: int
    _default_grace: int | None
    _verify_percent: float
    _in_flight: dict[str, asyncio.Future[Any]]
    _lock: asyncio.Lock

    async def query(
        self,
        *,
        key: str,
        tags: list[tuple[str, ...]],
        fn: Callable[[], Awaitable[T]],
        ttl: Duration | None = None,
        grace: Duration | None = None,
    ) -> T:
        """Fetch with caching, stampede protection, and SWR.

        Args:
            key: Cache key
            tags: Tags for invalidation
            fn: Async function to fetch data
            ttl: Time to live (default: client default)
            grace: Grace period for SWR (default: client default)

        Returns:
            Cached or fresh data
        """
        full_key = f"{self._prefix}:{key}"

        async def fetch() -> T:
            entry = await self._adapter.get(full_key)

            if entry is not None:
                stale = await self._is_stale(entry)
                expired = self._is_expired(entry)

                # Fresh and not stale - return immediately
                if not stale and not expired:
                    if self._should_verify():
                        asyncio.create_task(
                            self._run_verification(full_key, entry.value, fn)
                        )
                    return cast(T, entry.value)

                # Stale/expired but in grace - return stale, refresh bg
                if self._is_within_grace(entry):
                    asyncio.create_task(
                        self._refresh_in_background(full_key, tags, fn, ttl, grace)
                    )
                    return cast(T, entry.value)

            # Cache miss or outside grace - fetch synchronously
            value = await fn()
            await self._store(full_key, value, tags, ttl, grace)
            return value

        return await self._coalesce(full_key, fetch)

    async def get(self, key: str) -> Any | None:
        """Raw get - escape hatch for manual cache access."""
        full_key = f"{self._prefix}:{key}"
        entry = await self._adapter.get(full_key)
        if entry is None:
            return None
        if await self._is_stale(entry) or self._is_expired(entry):
            return None
        return entry.value

    async def set(
        self,
        key: str,
        value: T,
        *,
        tags: list[tuple[str, ...]],
        ttl: Duration,
        grace: Duration | None = None,
    ) -> None:
        """Raw set - escape hatch for manual cache population."""
        full_key = f"{self._prefix}:{key}"
        await self._store(full_key, value, tags, ttl, grace)

    async def delete(self, key: str) -> None:
        """Raw delete - escape hatch for manual cache removal."""
        full_key = f"{self._prefix}:{key}"
        await self._adapter.delete(full_key)

    async def invalidate(
        self,
        tags: list[tuple[str, ...]],
        *,
        exact: bool = False,
    ) -> None:
        """Invalidate cache entries by tags.

        By default, invalidating a tag also invalidates all entries
        with more specific tags (children).
        """
        _ = exact  # Reserved for future use
        now = int(time.time() * 1000)
        for tag in tags:
            await self._adapter.set_tag_invalidation_time(Tag(tag), now)

    async def clear(self) -> None:
        """Clear all cached entries."""
        await self._adapter.clear()

    async def disconnect(self) -> None:
        """Disconnect from the storage backend."""
        await self._adapter.disconnect()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _store(
        self,
        key: str,
        value: Any,
        tags: list[tuple[str, ...]],
        ttl: Duration | None,
        grace: Duration | None,
    ) -> None:
        now = int(time.time() * 1000)
        ttl_ms = parse_duration(ttl) if ttl else self._default_ttl
        grace_ms = parse_duration(grace) if grace else self._default_grace

        entry: CacheEntry[object] = CacheEntry(
            value=value,
            tags=[Tag(t) for t in tags],
            created_at=now,
            expires_at=now + ttl_ms,
            grace_until=now + ttl_ms + grace_ms if grace_ms else None,
        )
        await self._adapter.set(key, entry)

    async def _is_stale(self, entry: CacheEntry[Any]) -> bool:
        """Check if any tag has been invalidated since entry creation."""
        for tag in entry.tags:
            # Check exact invalidation
            inv_time = await self._adapter.get_tag_invalidation_time(tag)
            if inv_time is not None and inv_time >= entry.created_at:
                return True
            # Check prefix invalidations (all parent tags)
            for i in range(1, len(tag)):
                parent = Tag(tag[:i])
                inv_time = await self._adapter.get_tag_invalidation_time(parent)
                if inv_time is not None and inv_time >= entry.created_at:
                    return True
        return False

    def _is_expired(self, entry: CacheEntry[Any]) -> bool:
        """Check if entry has exceeded its TTL."""
        return time.time() * 1000 > entry.expires_at

    def _is_within_grace(self, entry: CacheEntry[Any]) -> bool:
        """Check if entry is within its grace period."""
        if entry.grace_until is None:
            return False
        return time.time() * 1000 <= entry.grace_until

    def _should_verify(self) -> bool:
        """Determine if we should verify this cache hit."""
        if not isinstance(self._adapter, AsyncVerifiableAdapter):
            return False
        if self._verify_percent <= 0:
            return False
        if self._verify_percent >= 1:
            return True
        return random.random() < self._verify_percent

    async def _run_verification(
        self,
        key: str,
        cached_value: Any,
        fn: Callable[[], Awaitable[Any]],
    ) -> None:
        """Run verification in background."""
        try:
            fresh_value = await fn()
            cached_hash = hashlib.sha256(
                json.dumps(cached_value, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            fresh_hash = hashlib.sha256(
                json.dumps(fresh_value, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            is_stale = cached_hash != fresh_hash
            if isinstance(self._adapter, AsyncVerifiableAdapter):
                await self._adapter.report_verification(
                    key, is_stale, cached_hash, fresh_hash
                )
        except Exception:
            pass  # Silently fail verification

    async def _refresh_in_background(
        self,
        key: str,
        tags: list[tuple[str, ...]],
        fn: Callable[[], Awaitable[Any]],
        ttl: Duration | None,
        grace: Duration | None,
    ) -> None:
        """Refresh cache entry in background."""
        try:
            value = await fn()
            await self._store(key, value, tags, ttl, grace)
        except Exception:
            pass  # Silently fail background refresh

    async def _coalesce(
        self, key: str, fetch: Callable[[], Awaitable[T]]
    ) -> T:
        """Coalesce concurrent requests for same key (stampede protection)."""
        async with self._lock:
            if key in self._in_flight:
                future = self._in_flight[key]
                return await future

            future: asyncio.Future[T] = asyncio.get_event_loop().create_future()
            self._in_flight[key] = future

        try:
            result = await fetch()
            future.set_result(result)
            return result
        except BaseException as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                del self._in_flight[key]


def create_primitives(
    *,
    adapter: AsyncStorageAdapter,
    prefix: str = "t87s",
    default_ttl: Duration = "30s",
    default_grace: Duration | None = None,
    verify_percent: float = 0.1,
) -> Primitives:
    """Create a cache primitives instance.

    Args:
        adapter: Storage adapter
        prefix: Key prefix for all cache entries
        default_ttl: Default time to live
        default_grace: Default grace period for SWR
        verify_percent: Percentage of hits to verify (0.0-1.0)

    Returns:
        Primitives instance with query, get, set, del, invalidate, clear, disconnect
    """
    if not 0 <= verify_percent <= 1:
        raise ValueError("verify_percent must be between 0 and 1")

    return Primitives(
        _adapter=adapter,
        _prefix=prefix,
        _default_ttl=parse_duration(default_ttl),
        _default_grace=parse_duration(default_grace) if default_grace else None,
        _verify_percent=verify_percent,
        _in_flight={},
        _lock=asyncio.Lock(),
    )


__all__ = ["Primitives", "create_primitives"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_primitives.py -v`
Expected: PASS

**Step 5: Run mypy**

Run: `mypy src/t87s/primitives.py`
Expected: No errors

**Step 6: Commit**

```bash
git add src/t87s/primitives.py tests/test_primitives.py
git commit -m "feat(python): add create_primitives() with stampede protection and SWR

Implements async primitives API matching TS:
- query(): Cached fetch with stampede protection
- get/set/del: Raw escape hatches
- invalidate(): Tag-based with hierarchical support
- clear/disconnect: Lifecycle methods

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create QueryCache Class

**Files:**
- Create: `src/t87s/query_cache.py`
- Test: `tests/test_query_cache.py`

**Step 1: Write the failing tests**

```python
# tests/test_query_cache.py
"""Tests for QueryCache with @cached decorator."""

from dataclasses import dataclass
from typing import Any

import pytest

from t87s import AsyncMemoryAdapter
from t87s.query_cache import QueryCache, cached
from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_query_cache.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# src/t87s/query_cache.py
"""QueryCache - typed cache with schema-based tags.

Provides:
- QueryCache[SchemaT]: Base class for defining typed caches
- @cached(*specs): Decorator for cached query methods
- .t property: Schema instance for runtime tag construction
- .primitives: Escape hatch to raw operations
- .invalidate(): Accept TypedTags for invalidation
"""

from __future__ import annotations

import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
)

from t87s.adapters.base import AsyncStorageAdapter
from t87s.primitives import Primitives, create_primitives
from t87s.schema import StaticTagSpec, TagSchema, TagSpec, WildTagSpec
from t87s.typed_tag import TypedTag
from t87s.types import Duration

SchemaT = TypeVar("SchemaT", bound=TagSchema)

# Type for specs that @cached accepts
CacheableSpec = TagSpec | WildTagSpec[Any] | StaticTagSpec | TagSchema


def _to_tag_spec(spec: CacheableSpec) -> TagSpec:
    """Convert any cacheable spec to TagSpec."""
    if isinstance(spec, TagSpec):
        return spec
    elif isinstance(spec, (WildTagSpec, StaticTagSpec)):
        return spec._spec
    else:
        raise TypeError(f"Expected TagSpec, got {type(spec)}")


class QueryDescriptor:
    """Descriptor that wraps cached methods."""

    def __init__(self, fn: Any, specs: tuple[CacheableSpec, ...]) -> None:
        self._fn = fn
        self._tag_specs = tuple(_to_tag_spec(s) for s in specs)
        self._name = fn.__name__

        # Validate wild count matches param count
        sig = inspect.signature(fn)
        param_count = len([p for p in sig.parameters.keys() if p != "self"])
        max_wilds = max((spec.wild_count for spec in self._tag_specs), default=0)

        if max_wilds != param_count:
            raise TypeError(
                f"@cached on {fn.__name__}: specs have {max_wilds} wilds "
                f"but method has {param_count} params (excluding self)"
            )

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, owner: type) -> Any:
        if obj is None:
            return self
        return BoundQuery(self, obj)


class BoundQuery:
    """A query method bound to a cache instance."""

    __slots__ = ("_descriptor", "_cache")

    def __init__(self, descriptor: QueryDescriptor, cache: QueryCache[Any]) -> None:
        self._descriptor = descriptor
        self._cache = cache

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Build tags from specs
        tags = [
            spec.build_path(args[: spec.wild_count])
            for spec in self._descriptor._tag_specs
        ]

        # Build cache key
        cache_key = f"{self._descriptor._name}:{args}:{kwargs}"

        # Create fetch function that calls the original method
        async def fetch() -> Any:
            return await self._descriptor._fn(self._cache, *args, **kwargs)

        return await self._cache.primitives.query(
            key=cache_key,
            tags=tags,
            fn=fetch,
        )


def cached(*specs: CacheableSpec) -> Any:
    """Decorator for cached query methods.

    Usage:
        class MyCache(QueryCache[MyTags]):
            @cached(MyTags.users())
            async def get_user(self, id: str) -> User:
                return await fetch_user(id)

    The number of wild segments in specs must match the number
    of method parameters (excluding self).
    """

    def decorator(fn: Any) -> QueryDescriptor:
        return QueryDescriptor(fn, specs)

    return decorator


class QueryCache(Generic[SchemaT]):
    """Base class for typed query caches.

    Subclass and add @cached methods:

        class MyCache(QueryCache[MyTags]):
            @cached(MyTags.users())
            async def get_user(self, id: str) -> User:
                return await fetch_user(id)

    Usage:
        cache = MyCache(adapter=AsyncMemoryAdapter())
        user = await cache.get_user("123")
        await cache.invalidate(cache.t.users("123"))
    """

    _schema_type: type[SchemaT]
    _t: SchemaT
    _primitives: Primitives

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Extract schema type from Generic parameter
        for base in getattr(cls, "__orig_bases__", ()):
            origin = get_origin(base)
            if origin is QueryCache:
                args = get_args(base)
                if args:
                    cls._schema_type = args[0]
                    break

    def __init__(
        self,
        *,
        adapter: AsyncStorageAdapter,
        prefix: str = "t87s",
        default_ttl: Duration = "30s",
        default_grace: Duration | None = None,
        verify_percent: float = 0.1,
    ) -> None:
        if hasattr(self, "_schema_type"):
            self._t = self._schema_type()

        self._primitives = create_primitives(
            adapter=adapter,
            prefix=prefix,
            default_ttl=default_ttl,
            default_grace=default_grace,
            verify_percent=verify_percent,
        )

    @property
    def t(self) -> SchemaT:
        """Schema instance for runtime tag construction.

        Usage:
            cache.t.users("123")  # Returns a navigable tag path
        """
        return self._t

    @property
    def primitives(self) -> Primitives:
        """Escape hatch to raw cache primitives.

        Usage:
            await cache.primitives.set("manual", value, tags=[], ttl="1h")
        """
        return self._primitives

    async def invalidate(self, *tags: TypedTag | TagSchema) -> None:
        """Invalidate cache entries by tags.

        Usage:
            await cache.invalidate(cache.t.users("123"))
            await cache.invalidate(cache.t.posts("p1").comments("c1"))
        """
        paths = []
        for tag in tags:
            if isinstance(tag, TypedTag):
                paths.append(tag.path)
            elif isinstance(tag, TagSchema):
                paths.append(tag.path)
            else:
                raise TypeError(f"Expected TypedTag or TagSchema, got {type(tag)}")

        await self._primitives.invalidate(paths)


__all__ = ["QueryCache", "cached"]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_query_cache.py -v`
Expected: PASS

**Step 5: Run mypy**

Run: `mypy src/t87s/query_cache.py`
Expected: No errors

**Step 6: Commit**

```bash
git add src/t87s/query_cache.py tests/test_query_cache.py
git commit -m "feat(python): add QueryCache with @cached decorator

Implements typed query cache matching TS QueryCache:
- QueryCache[SchemaT] base class
- @cached(*specs) decorator with wild count validation
- .t property for runtime tag construction
- .primitives escape hatch
- .invalidate() with TypedTag support

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Update Package Exports

**Files:**
- Modify: `src/t87s/__init__.py`

**Step 1: Write the failing test**

```python
# tests/test_exports.py
"""Tests for package exports."""


def test_new_exports_available() -> None:
    """Test that new QueryCache exports are available."""
    from t87s import (
        Primitives,
        QueryCache,
        Static,
        TagSchema,
        TypedTag,
        Wild,
        cached,
        create_primitives,
    )

    # Just verify they're importable
    assert Primitives is not None
    assert QueryCache is not None
    assert TagSchema is not None
    assert Wild is not None
    assert Static is not None
    assert TypedTag is not None
    assert cached is not None
    assert create_primitives is not None


def test_old_exports_still_work() -> None:
    """Test that old API exports still work."""
    from t87s import (
        AsyncMemoryAdapter,
        AsyncQueryConfig,
        AsyncT87s,
        MemoryAdapter,
        MutationResult,
        QueryConfig,
        T87s,
        define_tags,
    )

    # Just verify they're importable
    assert T87s is not None
    assert AsyncT87s is not None
    assert MemoryAdapter is not None
    assert AsyncMemoryAdapter is not None
    assert QueryConfig is not None
    assert AsyncQueryConfig is not None
    assert MutationResult is not None
    assert define_tags is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_exports.py -v`
Expected: FAIL with "ImportError"

**Step 3: Update __init__.py**

```python
# src/t87s/__init__.py
"""t87s - Declarative cache invalidation for Python."""

from contextlib import suppress

# Core types
from t87s.types import (
    AsyncQueryConfig,
    CacheEntry,
    Duration,
    MutationResult,
    QueryConfig,
    Tag,
)

# Duration parsing
from t87s.duration import parse_duration

# Old API (still supported)
from t87s.tags import define_tags, deserialize_tag, is_tag_prefix, serialize_tag
from t87s.client import T87s
from t87s.async_client import AsyncT87s

# New API: Primitives
from t87s.primitives import Primitives, create_primitives

# New API: QueryCache
from t87s.query_cache import QueryCache, cached
from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag

# Adapters
from t87s.adapters import (
    AsyncMemoryAdapter,
    AsyncStorageAdapter,
    MemoryAdapter,
    StorageAdapter,
    VerifiableAdapter,
)

# Optional adapter imports - only available when dependencies are installed
with suppress(ImportError):
    from t87s.adapters import AsyncRedisAdapter, RedisAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncUpstashAdapter, UpstashAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncCloudAdapter, CloudAdapter

__version__ = "0.1.0"

__all__ = [
    # New API: Primitives
    "Primitives",
    "create_primitives",
    # New API: QueryCache
    "QueryCache",
    "cached",
    "TagSchema",
    "Wild",
    "Static",
    "TypedTag",
    # Old API (still supported)
    "T87s",
    "AsyncT87s",
    "define_tags",
    "deserialize_tag",
    "is_tag_prefix",
    "serialize_tag",
    # Adapters
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncUpstashAdapter",
    "CloudAdapter",
    "MemoryAdapter",
    "RedisAdapter",
    "StorageAdapter",
    "UpstashAdapter",
    "VerifiableAdapter",
    # Types
    "AsyncQueryConfig",
    "CacheEntry",
    "Duration",
    "MutationResult",
    "QueryConfig",
    "Tag",
    "parse_duration",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_exports.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `pytest -v`
Expected: All tests pass

**Step 6: Run quality checks**

Run: `ruff check src tests --fix && ruff format src tests && mypy src`
Expected: No errors

**Step 7: Commit**

```bash
git add src/t87s/__init__.py tests/test_exports.py
git commit -m "feat(python): export new QueryCache and Primitives APIs

Adds exports for:
- create_primitives, Primitives
- QueryCache, cached
- TagSchema, Wild, Static, TypedTag

Maintains backward compatibility with old T87s API.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Integration Test - Full Workflow

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_integration.py
"""Integration tests for the complete QueryCache workflow."""

from dataclasses import dataclass
from typing import Any

import pytest

from t87s import (
    AsyncMemoryAdapter,
    QueryCache,
    Static,
    TagSchema,
    Wild,
    cached,
    create_primitives,
)


@dataclass
class User:
    id: str
    name: str


@dataclass
class Post:
    id: str
    title: str
    author_id: str


@dataclass
class Comment:
    id: str
    post_id: str
    text: str


# Realistic schema
class CommentChildren(TagSchema):
    pass


class PostChildren(TagSchema):
    comments: Wild[CommentChildren]
    metadata: Static


class UserChildren(TagSchema):
    posts: Wild[PostChildren]
    profile: Static


class AppTags(TagSchema):
    users: Wild[UserChildren]
    posts: Wild[PostChildren]
    config: Static


class TestFullWorkflow:
    """Test complete realistic workflow."""

    async def test_blog_cache(self) -> None:
        """Simulate a blog application cache."""
        fetch_counts: dict[str, int] = {}

        class BlogCache(QueryCache[AppTags]):
            @cached(AppTags.users())
            async def get_user(self, id: str) -> User:
                fetch_counts["user"] = fetch_counts.get("user", 0) + 1
                return User(id=id, name=f"User {id}")

            @cached(AppTags.posts(), AppTags.users().posts())
            async def get_post(self, post_id: str) -> Post:
                fetch_counts["post"] = fetch_counts.get("post", 0) + 1
                return Post(id=post_id, title=f"Post {post_id}", author_id="u1")

            @cached(AppTags.posts().comments())
            async def get_comments(self, post_id: str, comment_id: str) -> Comment:
                fetch_counts["comment"] = fetch_counts.get("comment", 0) + 1
                return Comment(id=comment_id, post_id=post_id, text="Great post!")

            @cached(AppTags.config)
            async def get_config(self) -> dict[str, Any]:
                fetch_counts["config"] = fetch_counts.get("config", 0) + 1
                return {"theme": "dark", "lang": "en"}

        cache = BlogCache(adapter=AsyncMemoryAdapter())

        # Initial fetches
        user = await cache.get_user("u1")
        assert user.name == "User u1"
        assert fetch_counts["user"] == 1

        post = await cache.get_post("p1")
        assert post.title == "Post p1"
        assert fetch_counts["post"] == 1

        comment = await cache.get_comments("p1", "c1")
        assert comment.text == "Great post!"
        assert fetch_counts["comment"] == 1

        config = await cache.get_config()
        assert config["theme"] == "dark"
        assert fetch_counts["config"] == 1

        # Cache hits - no new fetches
        await cache.get_user("u1")
        await cache.get_post("p1")
        await cache.get_comments("p1", "c1")
        await cache.get_config()
        assert fetch_counts["user"] == 1
        assert fetch_counts["post"] == 1
        assert fetch_counts["comment"] == 1
        assert fetch_counts["config"] == 1

        # Invalidate specific user
        await cache.invalidate(cache.t.users("u1"))
        await cache.get_user("u1")
        assert fetch_counts["user"] == 2

        # Invalidate post - should also invalidate comments
        await cache.invalidate(cache.t.posts("p1"))
        await cache.get_post("p1")
        await cache.get_comments("p1", "c1")
        assert fetch_counts["post"] == 2
        assert fetch_counts["comment"] == 2

    async def test_primitives_escape_hatch(self) -> None:
        """Test using primitives for manual cache operations."""

        class MyCache(QueryCache[AppTags]):
            pass

        cache = MyCache(adapter=AsyncMemoryAdapter())

        # Manual set/get
        await cache.primitives.set(
            "manual:key",
            {"custom": "data"},
            tags=[("manual",)],
            ttl="1h",
        )

        result = await cache.primitives.get("manual:key")
        assert result == {"custom": "data"}

        # Manual invalidation
        await cache.primitives.invalidate([("manual",)])
        result = await cache.primitives.get("manual:key")
        assert result is None

    async def test_standalone_primitives(self) -> None:
        """Test primitives without QueryCache."""
        adapter = AsyncMemoryAdapter()
        cache = create_primitives(adapter=adapter, default_ttl="10s")

        fetch_count = 0

        async def fetch_data() -> dict[str, str]:
            nonlocal fetch_count
            fetch_count += 1
            return {"value": "data"}

        # Query
        result = await cache.query(
            key="my-key",
            tags=[("data",)],
            fn=fetch_data,
        )
        assert result == {"value": "data"}
        assert fetch_count == 1

        # Cache hit
        result = await cache.query(
            key="my-key",
            tags=[("data",)],
            fn=fetch_data,
        )
        assert fetch_count == 1

        # Invalidate and refetch
        await cache.invalidate([("data",)])
        result = await cache.query(
            key="my-key",
            tags=[("data",)],
            fn=fetch_data,
        )
        assert fetch_count == 2
```

**Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(python): add integration tests for QueryCache workflow

Tests realistic blog cache scenario with:
- Multiple cached methods
- Hierarchical tag invalidation
- Primitives escape hatch
- Standalone primitives usage

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Final Quality Checks and Cleanup

**Step 1: Run all linting**

Run: `ruff check src tests --fix && ruff format src tests`
Expected: No changes needed

**Step 2: Run type checking**

Run: `mypy src`
Expected: No errors

**Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 4: Remove spike32 file (now replaced by production code)**

Run: `rm src/t87s/query_cache_spike32.py`

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore(python): remove spike32, finalize QueryCache implementation

- Removed experimental spike file (now in production modules)
- All tests passing
- Mypy strict mode passing
- Ruff linting passing

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Remove Old API (Definition of Done)

The old API (`T87s`, `AsyncT87s`, `define_tags`, `QueryConfig`, `MutationResult`) is now superseded by the new primitives + QueryCache API. Remove the old implementation to keep the codebase clean.

**Files to DELETE:**
- `src/t87s/client.py` — Old sync T87s class
- `src/t87s/async_client.py` — Old async AsyncT87s class
- `src/t87s/tags.py` — Old define_tags, serialize_tag, deserialize_tag
- `tests/test_client.py` — Tests for old sync client
- `tests/test_async_client.py` — Tests for old async client
- `tests/test_tags.py` — Tests for old tag utilities

**Files to UPDATE:**
- `src/t87s/__init__.py` — Remove old exports
- `src/t87s/types.py` — Remove QueryConfig, AsyncQueryConfig, MutationResult (keep CacheEntry, Tag, Duration)

**Step 1: Delete old source files**

```bash
rm src/t87s/client.py
rm src/t87s/async_client.py
rm src/t87s/tags.py
```

**Step 2: Delete old test files**

```bash
rm tests/test_client.py
rm tests/test_async_client.py
rm tests/test_tags.py
```

**Step 3: Update types.py - remove old types**

Keep only:
- `Tag` (used by new API)
- `CacheEntry` (used by adapters)
- `Duration` (used everywhere)

Remove:
- `QueryConfig`
- `AsyncQueryConfig`
- `MutationResult`

**Step 4: Update __init__.py - remove old exports**

```python
# src/t87s/__init__.py
"""t87s - Declarative cache invalidation for Python."""

from contextlib import suppress

# Core types
from t87s.types import CacheEntry, Duration, Tag

# Duration parsing
from t87s.duration import parse_duration

# Primitives API
from t87s.primitives import Primitives, create_primitives

# QueryCache API
from t87s.query_cache import QueryCache, cached
from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag

# Adapters
from t87s.adapters import (
    AsyncMemoryAdapter,
    AsyncStorageAdapter,
    MemoryAdapter,
    StorageAdapter,
    VerifiableAdapter,
)

# Optional adapter imports
with suppress(ImportError):
    from t87s.adapters import AsyncRedisAdapter, RedisAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncUpstashAdapter, UpstashAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncCloudAdapter, CloudAdapter

__version__ = "0.1.0"

__all__ = [
    # Primitives API
    "Primitives",
    "create_primitives",
    # QueryCache API
    "QueryCache",
    "cached",
    "TagSchema",
    "Wild",
    "Static",
    "TypedTag",
    # Adapters
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncUpstashAdapter",
    "CloudAdapter",
    "MemoryAdapter",
    "RedisAdapter",
    "StorageAdapter",
    "UpstashAdapter",
    "VerifiableAdapter",
    # Types
    "CacheEntry",
    "Duration",
    "Tag",
    "parse_duration",
]
```

**Step 5: Update test_exports.py**

Remove `test_old_exports_still_work` test, keep only `test_new_exports_available`.

**Step 6: Run tests to verify nothing broke**

```bash
pytest -v
```

Expected: All remaining tests pass

**Step 7: Run quality checks**

```bash
ruff check src tests --fix && ruff format src tests
mypy src
```

**Step 8: Commit the cleanup**

```bash
git add -A
git commit -m "refactor(python): remove old T87s API, keep only primitives + QueryCache

BREAKING CHANGE: Removed old API in favor of new typed API:

Removed:
- T87s, AsyncT87s classes
- define_tags(), QueryConfig, AsyncQueryConfig, MutationResult
- serialize_tag(), deserialize_tag(), is_tag_prefix()

Migration:
- T87s.query() → create_primitives().query() or QueryCache @cached
- define_tags() → class MyTags(TagSchema) with Wild[T]/Static
- MutationResult → call cache.invalidate() directly after mutation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | TypedTag dataclass | test_typed_tag.py |
| 2 | Schema system (TagSchema, Wild, Static) | test_schema.py |
| 3 | Async Primitives | test_primitives.py |
| 4 | QueryCache with @cached | test_query_cache.py |
| 5 | Update package exports | test_exports.py |
| 6 | Integration tests | test_integration.py |
| 7 | Quality checks and cleanup | - |
| 8 | **Remove old API (Definition of Done)** | - |

**After completing all tasks:**

```bash
# Verify everything works
cd /home/mikesol/Documents/GitHub/t87s/t87s/.worktrees/maximalist-types-spike/packages/python
source .venv/bin/activate
ruff check src tests
ruff format --check src tests
mypy src
pytest -v

# Create PR
git push -u origin feat/query-cache-design
```

---

## References

| Resource | Location |
|----------|----------|
| Design doc | `docs/plans/2026-01-30-query-cache-python-design.md` |
| Golden spike | `src/t87s/query_cache_spike32.py` (remove after implementation) |
| TS primitives | `packages/core/src/primitives.ts` |
| TS QueryCache | `packages/core/src/query-cache.ts` |
| Existing tests | `tests/test_client.py` (pattern reference) |
