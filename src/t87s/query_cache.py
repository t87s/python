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
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
)

from t87s.adapters.base import AsyncStorageAdapter
from t87s.primitives import Primitives, create_primitives
from t87s.schema import StaticTagSpec, TagSchema, TagSpec, WildNode, WildTagSpec
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
        param_count = len([p for p in sig.parameters if p != "self"])
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

    __slots__ = ("_cache", "_descriptor")

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

    async def invalidate(self, *tags: TypedTag | TagSchema | WildNode[Any]) -> None:
        """Invalidate cache entries by tags.

        Usage:
            await cache.invalidate(cache.t.users("123"))
            await cache.invalidate(cache.t.posts("p1").comments("c1"))
            await cache.invalidate(cache.t.posts)  # Invalidate all posts
        """
        paths = []
        for tag in tags:
            if isinstance(tag, (TypedTag, TagSchema, WildNode)):
                paths.append(tag.path)
            else:
                raise TypeError(f"Expected TypedTag or TagSchema, got {type(tag)}")

        await self._primitives.invalidate(paths)


__all__ = ["QueryCache", "cached"]
