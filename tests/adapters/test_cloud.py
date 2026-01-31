"""Tests for Cloud adapter using mocked HTTP responses."""

import pytest

# Skip all tests if httpx is not installed
pytest.importorskip("httpx")

import httpx
import respx

from t87s import CacheEntry, Tag
from t87s.adapters.cloud import AsyncCloudAdapter


@pytest.fixture
def async_cloud_adapter() -> AsyncCloudAdapter:
    """Create an AsyncCloudAdapter with test configuration."""
    return AsyncCloudAdapter(api_key="test-api-key", base_url="https://api.test.dev")


class TestAsyncCloudAdapter:
    """Tests for async AsyncCloudAdapter with mocked responses."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_returns_entry(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test getting a cached entry."""
        respx.post("https://api.test.dev/v1/cache/get").mock(
            return_value=httpx.Response(
                200,
                json={
                    "entry": {
                        "value": {"id": "456"},
                        "tags": [["post", "456"]],
                        "createdAt": 2000,
                        "expiresAt": 3000,
                        "graceUntil": 4000,
                    }
                },
            )
        )

        result = await async_cloud_adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "456"}
        assert result.grace_until == 4000

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_returns_none_on_missing_entry(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test that missing entry returns None."""
        respx.post("https://api.test.dev/v1/cache/get").mock(
            return_value=httpx.Response(200, json={"entry": None})
        )

        result = await async_cloud_adapter.get("nonexistent")
        assert result is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_set_sends_entry(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test setting a cached entry."""
        route = respx.post("https://api.test.dev/v1/cache/set").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        entry: CacheEntry[object] = CacheEntry(
            value={"id": "456"},
            tags=[Tag(("post", "456"))],
            created_at=2000,
            expires_at=3000,
            grace_until=None,
        )
        await async_cloud_adapter.set("key1", entry)

        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_sends_request(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test deleting a cached entry."""
        route = respx.post("https://api.test.dev/v1/cache/delete").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await async_cloud_adapter.delete("key1")
        assert route.called

    @pytest.mark.asyncio
    async def test_get_tag_invalidation_time_returns_none(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test that get_tag_invalidation_time returns None (server-side check)."""
        result = await async_cloud_adapter.get_tag_invalidation_time(
            Tag(("post", "456"))
        )
        assert result is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_set_tag_invalidation_time(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test setting tag invalidation time via /v1/invalidate."""
        route = respx.post("https://api.test.dev/v1/invalidate").mock(
            return_value=httpx.Response(200, json={"ok": True, "invalidatedAt": 4000})
        )

        await async_cloud_adapter.set_tag_invalidation_time(Tag(("post", "456")), 4000)
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_clear_sends_request(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test clearing all cached entries."""
        route = respx.post("https://api.test.dev/v1/clear").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await async_cloud_adapter.clear()
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_report_verification(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test reporting verification result."""
        route = respx.post("https://api.test.dev/v1/verify").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await async_cloud_adapter.report_verification(
            key="key1",
            is_stale=False,
            cached_hash="abc123",
            fresh_hash="abc123",
        )

        assert route.called
