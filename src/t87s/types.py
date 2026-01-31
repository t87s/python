"""Core types for t87s cache library."""

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


# Duration type alias
Duration = str | int  # "30s", "5m", "2h", "1d" or milliseconds
