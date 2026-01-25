"""Core types for t87s cache library."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Generic,
    NewType,
    TypeVar,
)

T = TypeVar("T")

# Branded tag type - compile-time enforcement only (like TypeScript)
if TYPE_CHECKING:
    Tag = NewType("Tag", tuple[str, ...])
else:
    Tag = tuple


@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[T]):
    """A cached value with metadata."""

    value: T
    tags: list[Tag]
    created_at: int  # Unix timestamp ms
    expires_at: int  # TTL expiration
    grace_until: int | None  # Grace period expiration


@dataclass(frozen=True, slots=True)
class QueryConfig(Generic[T]):
    """Configuration for a cached query (sync)."""

    tags: list[Tag]
    ttl: str | int  # "5m" or milliseconds
    fn: Callable[[], T]
    grace: str | int | None = None


@dataclass(frozen=True, slots=True)
class AsyncQueryConfig(Generic[T]):
    """Configuration for a cached query (async)."""

    tags: list[Tag]
    ttl: str | int  # "5m" or milliseconds
    fn: Callable[[], Awaitable[T]]
    grace: str | int | None = None


@dataclass(frozen=True, slots=True)
class MutationResult(Generic[T]):
    """Result of a mutation with tags to invalidate."""

    result: T
    invalidates: list[Tag]


# Duration type alias
Duration = str | int  # "30s", "5m", "2h", "1d" or milliseconds
