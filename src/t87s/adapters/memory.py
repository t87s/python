"""In-memory storage adapters."""

import asyncio
from collections import OrderedDict

from t87s.tags import serialize_tag
from t87s.types import CacheEntry, Tag


class MemoryAdapter:
    """Sync in-memory storage adapter with optional LRU eviction."""

    def __init__(self, max_items: int | None = None) -> None:
        self._cache: OrderedDict[str, CacheEntry[object]] = OrderedDict()
        self._invalidations: dict[str, int] = {}
        self._max_items = max_items

    def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        entry = self._cache.get(key)
        if entry:
            self._cache.move_to_end(key)  # LRU touch
        return entry

    def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        self._cache[key] = entry
        self._cache.move_to_end(key)
        if self._max_items and len(self._cache) > self._max_items:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        self._cache.pop(key, None)

    def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        key = serialize_tag(tag)
        return self._invalidations.get(key)

    def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        key = serialize_tag(tag)
        self._invalidations[key] = timestamp

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._invalidations.clear()

    def disconnect(self) -> None:
        """Disconnect from the storage backend (no-op for memory)."""
        pass


class AsyncMemoryAdapter:
    """Async in-memory storage adapter with optional LRU eviction."""

    def __init__(self, max_items: int | None = None) -> None:
        self._cache: OrderedDict[str, CacheEntry[object]] = OrderedDict()
        self._invalidations: dict[str, int] = {}
        self._max_items = max_items
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry:
                self._cache.move_to_end(key)  # LRU touch
            return entry

    async def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        async with self._lock:
            self._cache[key] = entry
            self._cache.move_to_end(key)
            if self._max_items and len(self._cache) > self._max_items:
                self._cache.popitem(last=False)

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        async with self._lock:
            self._cache.pop(key, None)

    async def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        key = serialize_tag(tag)
        async with self._lock:
            return self._invalidations.get(key)

    async def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        key = serialize_tag(tag)
        async with self._lock:
            self._invalidations[key] = timestamp

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()
            self._invalidations.clear()

    async def disconnect(self) -> None:
        """Disconnect from the storage backend (no-op for memory)."""
        pass
