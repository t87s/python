"""Sync cache client."""

import hashlib
import json
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from t87s.adapters.base import StorageAdapter
from t87s.duration import parse_duration
from t87s.types import CacheEntry, Duration, MutationResult, QueryConfig, Tag

P = ParamSpec("P")
R = TypeVar("R")


class T87s:
    """Sync cache client."""

    def __init__(
        self,
        adapter: StorageAdapter,
        *,
        prefix: str = "t87s",
        default_ttl: Duration = "30s",
        default_grace: Duration | None = None,
    ) -> None:
        self._adapter = adapter
        self._prefix = prefix
        self._default_ttl = parse_duration(default_ttl)
        self._default_grace = (
            parse_duration(default_grace) if default_grace is not None else None
        )
        self._in_flight: dict[str, threading.Event] = {}
        self._in_flight_results: dict[str, Any] = {}
        self._in_flight_errors: dict[str, BaseException] = {}
        self._lock = threading.Lock()

    def _make_cache_key(self, fn_name: str, args: tuple[Any, ...]) -> str:
        """Generate a cache key from function name and arguments."""
        args_hash = hashlib.sha256(
            json.dumps(args, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        return f"{self._prefix}:{fn_name}:{args_hash}"

    def _is_stale(self, entry: CacheEntry[Any]) -> bool:
        """Check if any tag has been invalidated since entry creation."""
        for tag in entry.tags:
            # Check exact invalidation
            inv_time = self._adapter.get_tag_invalidation_time(tag)
            if inv_time is not None and inv_time >= entry.created_at:
                return True
            # Check prefix invalidations (all parent tags)
            for i in range(1, len(tag)):
                parent = Tag(tag[:i])
                inv_time = self._adapter.get_tag_invalidation_time(parent)
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

    def _coalesce(self, key: str, fetch: Callable[[], R]) -> R:
        """Coalesce concurrent requests for same key."""
        with self._lock:
            if key in self._in_flight:
                event = self._in_flight[key]
                waiting = True
            else:
                event = threading.Event()
                self._in_flight[key] = event
                waiting = False

        if waiting:
            event.wait()
            with self._lock:
                if key in self._in_flight_errors:
                    error = self._in_flight_errors.pop(key)
                    raise error
                return cast(R, self._in_flight_results.pop(key))

        try:
            result = fetch()
            with self._lock:
                self._in_flight_results[key] = result
            return result
        except BaseException as e:
            with self._lock:
                self._in_flight_errors[key] = e
            raise
        finally:
            with self._lock:
                del self._in_flight[key]
            event.set()

    def _refresh_in_background(
        self,
        key: str,
        config: QueryConfig[Any],
    ) -> None:
        """Refresh cache entry in a background thread."""

        def refresh() -> None:
            try:
                value = config.fn()
                now = int(time.time() * 1000)
                ttl = parse_duration(config.ttl)
                grace = (
                    parse_duration(config.grace)
                    if config.grace is not None
                    else self._default_grace
                )
                entry: CacheEntry[object] = CacheEntry(
                    value=value,
                    tags=config.tags,
                    created_at=now,
                    expires_at=now + ttl,
                    grace_until=now + ttl + grace if grace else None,
                )
                self._adapter.set(key, entry)
            except Exception:
                pass  # Silently fail background refresh

        thread = threading.Thread(target=refresh, daemon=True)
        thread.start()

    def query(
        self,
        fn: Callable[P, QueryConfig[R]],
    ) -> Callable[P, R]:
        """Decorator that creates a cached query function."""

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            config = fn(*args, **kwargs)
            key = self._make_cache_key(fn.__name__, args)

            def fetch() -> R:
                entry = self._adapter.get(key)

                if entry is not None:
                    stale = self._is_stale(entry)
                    expired = self._is_expired(entry)

                    # Fresh and not stale - return immediately
                    if not stale and not expired:
                        return cast(R, entry.value)

                    # Stale/expired but in grace - return stale, refresh bg
                    if self._is_within_grace(entry):
                        self._refresh_in_background(key, config)
                        return cast(R, entry.value)

                # Cache miss or outside grace - fetch synchronously
                value = config.fn()
                now = int(time.time() * 1000)
                ttl = parse_duration(config.ttl)
                grace = (
                    parse_duration(config.grace)
                    if config.grace is not None
                    else self._default_grace
                )
                new_entry: CacheEntry[object] = CacheEntry(
                    value=value,
                    tags=config.tags,
                    created_at=now,
                    expires_at=now + ttl,
                    grace_until=now + ttl + grace if grace else None,
                )
                self._adapter.set(key, new_entry)
                return value

            return self._coalesce(key, fetch)

        return wrapper

    def mutation(
        self,
        fn: Callable[P, MutationResult[R]],
    ) -> Callable[P, R]:
        """Decorator that executes and returns result, then invalidates tags."""

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = fn(*args, **kwargs)
            self.invalidate(result.invalidates)
            return result.result

        return wrapper

    def invalidate(
        self,
        tags: list[Tag],
        *,
        exact: bool = False,
    ) -> None:
        """Manually invalidate cache entries by tags.

        By default (exact=False), invalidating a tag also invalidates all
        entries with more specific tags (children). For example, invalidating
        ('user',) will invalidate entries tagged ('user', '123').

        With exact=True, only entries with the exact tag are invalidated.
        """
        _ = exact  # Reserved for future use
        now = int(time.time() * 1000)
        for tag in tags:
            self._adapter.set_tag_invalidation_time(tag, now)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._adapter.clear()
