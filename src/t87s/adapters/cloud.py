"""Cloud storage adapters for t87s cloud service."""

from __future__ import annotations

import time
from typing import Any, cast

from t87s.types import CacheEntry, Tag


class CloudAdapter:
    """Sync Cloud storage adapter with staleness verification support."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.t87s.dev",
    ) -> None:
        import httpx

        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _request(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the cloud API."""
        response = self._client.post(endpoint, json=body)
        if not response.is_success:
            try:
                error = response.json().get("error", "Request failed")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise RuntimeError(error)
        return cast(dict[str, Any], response.json())

    def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        data = self._request("/v1/cache/get", {"key": key})
        entry = data.get("entry")
        if entry is None:
            return None
        return CacheEntry(
            value=entry["value"],
            tags=[Tag(tuple(tag)) for tag in entry["tags"]],
            created_at=entry["createdAt"],
            expires_at=entry["expiresAt"],
            grace_until=entry.get("graceUntil"),
        )

    def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        self._request(
            "/v1/cache/set",
            {
                "key": key,
                "entry": {
                    "value": entry.value,
                    "tags": [list(tag) for tag in entry.tags],
                    "createdAt": entry.created_at,
                    "expiresAt": entry.expires_at,
                    "graceUntil": entry.grace_until,
                },
            },
        )

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        self._request("/v1/cache/delete", {"key": key})

    def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag.

        Note: This is rarely called directly. The cloud service checks
        tag invalidation times server-side during get().
        """
        # For now, return None. Could add a /v1/tag/get endpoint later.
        return None

    def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        # Invalidation is done via /v1/invalidate endpoint
        self._request("/v1/invalidate", {"tags": [list(tag)], "exact": True})

    def clear(self) -> None:
        """Clear all cached entries."""
        self._request("/v1/clear", {})

    def disconnect(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def report_verification(
        self,
        key: str,
        is_stale: bool,
        cached_hash: str,
        fresh_hash: str,
    ) -> None:
        """Report verification result to the cloud service."""
        self._request(
            "/v1/verify",
            {
                "key": key,
                "cachedHash": cached_hash,
                "freshHash": fresh_hash,
                "isStale": is_stale,
                "timestamp": int(time.time() * 1000),
            },
        )


class AsyncCloudAdapter:
    """Async Cloud storage adapter with staleness verification support."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.t87s.dev",
    ) -> None:
        import httpx

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _request(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make a POST request to the cloud API."""
        response = await self._client.post(endpoint, json=body)
        if not response.is_success:
            try:
                error = response.json().get("error", "Request failed")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise RuntimeError(error)
        return cast(dict[str, Any], response.json())

    async def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        data = await self._request("/v1/cache/get", {"key": key})
        entry = data.get("entry")
        if entry is None:
            return None
        return CacheEntry(
            value=entry["value"],
            tags=[Tag(tuple(tag)) for tag in entry["tags"]],
            created_at=entry["createdAt"],
            expires_at=entry["expiresAt"],
            grace_until=entry.get("graceUntil"),
        )

    async def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        await self._request(
            "/v1/cache/set",
            {
                "key": key,
                "entry": {
                    "value": entry.value,
                    "tags": [list(tag) for tag in entry.tags],
                    "createdAt": entry.created_at,
                    "expiresAt": entry.expires_at,
                    "graceUntil": entry.grace_until,
                },
            },
        )

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        await self._request("/v1/cache/delete", {"key": key})

    async def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag.

        Note: This is rarely called directly. The cloud service checks
        tag invalidation times server-side during get().
        """
        # For now, return None. Could add a /v1/tag/get endpoint later.
        return None

    async def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        # Invalidation is done via /v1/invalidate endpoint
        await self._request("/v1/invalidate", {"tags": [list(tag)], "exact": True})

    async def clear(self) -> None:
        """Clear all cached entries."""
        await self._request("/v1/clear", {})

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def report_verification(
        self,
        key: str,
        is_stale: bool,
        cached_hash: str,
        fresh_hash: str,
    ) -> None:
        """Report verification result to the cloud service."""
        await self._request(
            "/v1/verify",
            {
                "key": key,
                "cachedHash": cached_hash,
                "freshHash": fresh_hash,
                "isStale": is_stale,
                "timestamp": int(time.time() * 1000),
            },
        )
