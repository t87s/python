"""Base adapter protocols for storage backends (async only)."""

from typing import Protocol, runtime_checkable

from t87s.types import CacheEntry, Tag


@runtime_checkable
class AsyncStorageAdapter(Protocol):
    """Async storage adapter interface."""

    async def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        ...

    async def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        ...

    async def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        ...

    async def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        ...

    async def clear(self) -> None:
        """Clear all cached entries."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the storage backend."""
        ...


@runtime_checkable
class AsyncVerifiableAdapter(Protocol):
    """Optional mixin for async adapters that support staleness verification."""

    async def report_verification(
        self, key: str, is_stale: bool, cached_hash: str, fresh_hash: str
    ) -> None:
        """Report verification result to the backend."""
        ...
