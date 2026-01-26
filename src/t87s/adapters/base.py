"""Base adapter protocols for storage backends."""

from typing import Protocol, TypeVar, runtime_checkable

from t87s.types import CacheEntry, Tag

T = TypeVar("T")


@runtime_checkable
class StorageAdapter(Protocol):
    """Sync storage adapter interface."""

    def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        ...

    def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        ...

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        ...

    def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        ...

    def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        ...

    def clear(self) -> None:
        """Clear all cached entries."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the storage backend."""
        ...


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
class VerifiableAdapter(Protocol):
    """Optional mixin for sync adapters that support staleness verification."""

    def report_verification(
        self, key: str, is_stale: bool, cached_hash: str, fresh_hash: str
    ) -> None:
        """Report verification result to the backend."""
        ...


@runtime_checkable
class AsyncVerifiableAdapter(Protocol):
    """Optional mixin for async adapters that support staleness verification."""

    async def report_verification(
        self, key: str, is_stale: bool, cached_hash: str, fresh_hash: str
    ) -> None:
        """Report verification result to the backend."""
        ...
