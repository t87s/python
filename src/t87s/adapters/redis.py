"""Redis storage adapters."""

from __future__ import annotations

import json
from typing import Any

from t87s.tags import serialize_tag
from t87s.types import CacheEntry, Tag


def _serialize_entry(entry: CacheEntry[object]) -> str:
    """Serialize a cache entry to JSON."""
    return json.dumps(
        {
            "value": entry.value,
            "tags": [list(tag) for tag in entry.tags],
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
            "grace_until": entry.grace_until,
        }
    )


def _deserialize_entry(data: bytes | str) -> CacheEntry[object]:
    """Deserialize JSON to a cache entry."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    obj = json.loads(data)
    return CacheEntry(
        value=obj["value"],
        tags=[Tag(tuple(tag)) for tag in obj["tags"]],
        created_at=obj["created_at"],
        expires_at=obj["expires_at"],
        grace_until=obj["grace_until"],
    )


class RedisAdapter:
    """Sync Redis storage adapter."""

    def __init__(
        self,
        client: Any,  # redis.Redis
        *,
        prefix: str = "t87s",
    ) -> None:
        self._client = client
        self._prefix = prefix

    def _cache_key(self, key: str) -> str:
        """Generate full Redis key for cache entries."""
        return f"{self._prefix}:cache:{key}"

    def _tag_key(self, tag: Tag) -> str:
        """Generate full Redis key for tag invalidation times."""
        return f"{self._prefix}:tag:{serialize_tag(tag)}"

    def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        data = self._client.get(self._cache_key(key))
        if data is None:
            return None
        return _deserialize_entry(data)

    def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry with automatic expiration."""
        # Use grace_until if available, otherwise expires_at
        expire_at = entry.grace_until or entry.expires_at
        self._client.set(
            self._cache_key(key),
            _serialize_entry(entry),
            pxat=expire_at,
        )

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        self._client.delete(self._cache_key(key))

    def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        data = self._client.get(self._tag_key(tag))
        if data is None:
            return None
        return int(data)

    def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        # Tag invalidation times don't expire - they're used for comparison
        self._client.set(self._tag_key(tag), str(timestamp))

    def clear(self) -> None:
        """Clear all cached entries (but not tag invalidation times)."""
        # Use SCAN to find and delete all cache keys
        cursor = 0
        pattern = f"{self._prefix}:cache:*"
        while True:
            cursor, keys = self._client.scan(cursor, match=pattern, count=100)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def disconnect(self) -> None:
        """Close the Redis connection."""
        self._client.close()


class AsyncRedisAdapter:
    """Async Redis storage adapter."""

    def __init__(
        self,
        client: Any,  # redis.asyncio.Redis
        *,
        prefix: str = "t87s",
    ) -> None:
        self._client = client
        self._prefix = prefix

    def _cache_key(self, key: str) -> str:
        """Generate full Redis key for cache entries."""
        return f"{self._prefix}:cache:{key}"

    def _tag_key(self, tag: Tag) -> str:
        """Generate full Redis key for tag invalidation times."""
        return f"{self._prefix}:tag:{serialize_tag(tag)}"

    async def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        data = await self._client.get(self._cache_key(key))
        if data is None:
            return None
        return _deserialize_entry(data)

    async def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry with automatic expiration."""
        # Use grace_until if available, otherwise expires_at
        expire_at = entry.grace_until or entry.expires_at
        await self._client.set(
            self._cache_key(key),
            _serialize_entry(entry),
            pxat=expire_at,
        )

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        await self._client.delete(self._cache_key(key))

    async def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        data = await self._client.get(self._tag_key(tag))
        if data is None:
            return None
        return int(data)

    async def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        # Tag invalidation times don't expire - they're used for comparison
        await self._client.set(self._tag_key(tag), str(timestamp))

    async def clear(self) -> None:
        """Clear all cached entries (but not tag invalidation times)."""
        # Use SCAN to find and delete all cache keys
        cursor: int = 0
        pattern = f"{self._prefix}:cache:*"
        while True:
            result = await self._client.scan(cursor, match=pattern, count=100)
            cursor = result[0]
            keys = result[1]
            if keys:
                await self._client.delete(*keys)
            if cursor == 0:
                break

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        await self._client.aclose()
