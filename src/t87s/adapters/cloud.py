"""Cloud storage adapters for t87s cloud service."""

from __future__ import annotations

from t87s.tags import serialize_tag
from t87s.types import CacheEntry, Tag


class CloudAdapter:
    """Sync Cloud storage adapter with staleness verification support."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.t87s.dev",
        prefix: str = "t87s",
    ) -> None:
        import httpx

        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        self._prefix = prefix

    def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        response = self._client.get(f"/cache/{self._prefix}/{key}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return CacheEntry(
            value=data["value"],
            tags=[Tag(tuple(tag)) for tag in data["tags"]],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            grace_until=data.get("grace_until"),
        )

    def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        response = self._client.put(
            f"/cache/{self._prefix}/{key}",
            json={
                "value": entry.value,
                "tags": [list(tag) for tag in entry.tags],
                "created_at": entry.created_at,
                "expires_at": entry.expires_at,
                "grace_until": entry.grace_until,
            },
        )
        response.raise_for_status()

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        response = self._client.delete(f"/cache/{self._prefix}/{key}")
        # Ignore 404 - key might not exist
        if response.status_code != 404:
            response.raise_for_status()

    def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        serialized = serialize_tag(tag)
        response = self._client.get(f"/tags/{self._prefix}/{serialized}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return int(response.json()["timestamp"])

    def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        serialized = serialize_tag(tag)
        response = self._client.put(
            f"/tags/{self._prefix}/{serialized}",
            json={"timestamp": timestamp},
        )
        response.raise_for_status()

    def clear(self) -> None:
        """Clear all cached entries."""
        response = self._client.delete(f"/cache/{self._prefix}")
        response.raise_for_status()

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
        response = self._client.post(
            "/verify",
            json={
                "prefix": self._prefix,
                "key": key,
                "is_stale": is_stale,
                "cached_hash": cached_hash,
                "fresh_hash": fresh_hash,
            },
        )
        response.raise_for_status()


class AsyncCloudAdapter:
    """Async Cloud storage adapter with staleness verification support."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.t87s.dev",
        prefix: str = "t87s",
    ) -> None:
        import httpx

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        self._prefix = prefix

    async def get(self, key: str) -> CacheEntry[object] | None:
        """Get a cache entry by key."""
        response = await self._client.get(f"/cache/{self._prefix}/{key}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return CacheEntry(
            value=data["value"],
            tags=[Tag(tuple(tag)) for tag in data["tags"]],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            grace_until=data.get("grace_until"),
        )

    async def set(self, key: str, entry: CacheEntry[object]) -> None:
        """Store a cache entry."""
        response = await self._client.put(
            f"/cache/{self._prefix}/{key}",
            json={
                "value": entry.value,
                "tags": [list(tag) for tag in entry.tags],
                "created_at": entry.created_at,
                "expires_at": entry.expires_at,
                "grace_until": entry.grace_until,
            },
        )
        response.raise_for_status()

    async def delete(self, key: str) -> None:
        """Delete a cache entry."""
        response = await self._client.delete(f"/cache/{self._prefix}/{key}")
        # Ignore 404 - key might not exist
        if response.status_code != 404:
            response.raise_for_status()

    async def get_tag_invalidation_time(self, tag: Tag) -> int | None:
        """Get the invalidation timestamp for a tag."""
        serialized = serialize_tag(tag)
        response = await self._client.get(f"/tags/{self._prefix}/{serialized}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return int(response.json()["timestamp"])

    async def set_tag_invalidation_time(self, tag: Tag, timestamp: int) -> None:
        """Set the invalidation timestamp for a tag."""
        serialized = serialize_tag(tag)
        response = await self._client.put(
            f"/tags/{self._prefix}/{serialized}",
            json={"timestamp": timestamp},
        )
        response.raise_for_status()

    async def clear(self) -> None:
        """Clear all cached entries."""
        response = await self._client.delete(f"/cache/{self._prefix}")
        response.raise_for_status()

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
        response = await self._client.post(
            "/verify",
            json={
                "prefix": self._prefix,
                "key": key,
                "is_stale": is_stale,
                "cached_hash": cached_hash,
                "fresh_hash": fresh_hash,
            },
        )
        response.raise_for_status()
