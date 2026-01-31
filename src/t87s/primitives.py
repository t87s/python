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
from dataclasses import dataclass, field
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
    _in_flight: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

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
                        # Fire and forget - we don't await verification
                        asyncio.create_task(  # noqa: RUF006
                            self._run_verification(full_key, entry.value, fn)
                        )
                    return cast(T, entry.value)

                # Stale/expired but in grace - return stale, refresh bg
                if self._is_within_grace(entry):
                    # Fire and forget - we don't await background refresh
                    asyncio.create_task(  # noqa: RUF006
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

    async def _coalesce(self, key: str, fetch: Callable[[], Awaitable[T]]) -> T:
        """Coalesce concurrent requests for same key (stampede protection)."""
        # Check if there's already an in-flight request
        async with self._lock:
            if key in self._in_flight:
                existing_future = self._in_flight[key]
                # Wait for existing request outside the lock
                result: T = await existing_future
                return result

            # We're the first - create a future and register it
            loop = asyncio.get_event_loop()
            new_future: asyncio.Future[T] = loop.create_future()
            self._in_flight[key] = new_future

        try:
            result = await fetch()
            new_future.set_result(result)
            return result
        except BaseException as e:
            new_future.set_exception(e)
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
    )


__all__ = ["Primitives", "create_primitives"]
