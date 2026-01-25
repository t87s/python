"""Tests for Cloud adapters using mocked HTTP responses."""

import pytest

# Skip all tests if httpx is not installed
pytest.importorskip("httpx")

import httpx
import respx

from t87s import CacheEntry, Tag
from t87s.adapters.cloud import AsyncCloudAdapter, CloudAdapter


@pytest.fixture
def cloud_adapter() -> CloudAdapter:
    """Create a CloudAdapter with test configuration."""
    return CloudAdapter(
        api_key="test-api-key", base_url="https://api.test.dev", prefix="test"
    )


@pytest.fixture
def async_cloud_adapter() -> AsyncCloudAdapter:
    """Create an AsyncCloudAdapter with test configuration."""
    return AsyncCloudAdapter(
        api_key="test-api-key", base_url="https://api.test.dev", prefix="test"
    )


class TestCloudAdapter:
    """Tests for sync CloudAdapter with mocked responses."""

    @respx.mock
    def test_get_returns_entry(self, cloud_adapter: CloudAdapter) -> None:
        """Test getting a cached entry."""
        respx.get("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": {"id": "123"},
                    "tags": [["user", "123"]],
                    "created_at": 1000,
                    "expires_at": 2000,
                    "grace_until": None,
                },
            )
        )

        result = cloud_adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "123"}
        assert result.tags == [("user", "123")]
        assert result.created_at == 1000

    @respx.mock
    def test_get_returns_none_on_404(self, cloud_adapter: CloudAdapter) -> None:
        """Test that 404 returns None."""
        respx.get("https://api.test.dev/cache/test/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        result = cloud_adapter.get("nonexistent")
        assert result is None

    @respx.mock
    def test_set_sends_entry(self, cloud_adapter: CloudAdapter) -> None:
        """Test setting a cached entry."""
        route = respx.put("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(200)
        )

        entry: CacheEntry[object] = CacheEntry(
            value={"id": "123"},
            tags=[Tag(("user", "123"))],
            created_at=1000,
            expires_at=2000,
            grace_until=3000,
        )
        cloud_adapter.set("key1", entry)

        assert route.called
        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer test-api-key"

    @respx.mock
    def test_delete_sends_request(self, cloud_adapter: CloudAdapter) -> None:
        """Test deleting a cached entry."""
        route = respx.delete("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(200)
        )

        cloud_adapter.delete("key1")
        assert route.called

    @respx.mock
    def test_delete_ignores_404(self, cloud_adapter: CloudAdapter) -> None:
        """Test that delete ignores 404."""
        respx.delete("https://api.test.dev/cache/test/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        # Should not raise
        cloud_adapter.delete("nonexistent")

    @respx.mock
    def test_get_tag_invalidation_time(self, cloud_adapter: CloudAdapter) -> None:
        """Test getting tag invalidation time."""
        respx.get("https://api.test.dev/tags/test/user:123").mock(
            return_value=httpx.Response(200, json={"timestamp": 1000})
        )

        result = cloud_adapter.get_tag_invalidation_time(Tag(("user", "123")))
        assert result == 1000

    @respx.mock
    def test_get_tag_invalidation_time_returns_none_on_404(
        self, cloud_adapter: CloudAdapter
    ) -> None:
        """Test that 404 returns None for tag invalidation time."""
        respx.get("https://api.test.dev/tags/test/user:456").mock(
            return_value=httpx.Response(404)
        )

        result = cloud_adapter.get_tag_invalidation_time(Tag(("user", "456")))
        assert result is None

    @respx.mock
    def test_set_tag_invalidation_time(self, cloud_adapter: CloudAdapter) -> None:
        """Test setting tag invalidation time."""
        route = respx.put("https://api.test.dev/tags/test/user:123").mock(
            return_value=httpx.Response(200)
        )

        cloud_adapter.set_tag_invalidation_time(Tag(("user", "123")), 2000)
        assert route.called

    @respx.mock
    def test_clear_sends_request(self, cloud_adapter: CloudAdapter) -> None:
        """Test clearing all cached entries."""
        route = respx.delete("https://api.test.dev/cache/test").mock(
            return_value=httpx.Response(200)
        )

        cloud_adapter.clear()
        assert route.called

    @respx.mock
    def test_report_verification(self, cloud_adapter: CloudAdapter) -> None:
        """Test reporting verification result."""
        route = respx.post("https://api.test.dev/verify").mock(
            return_value=httpx.Response(200)
        )

        cloud_adapter.report_verification(
            key="key1",
            is_stale=True,
            cached_hash="abc123",
            fresh_hash="def456",
        )

        assert route.called
        request = route.calls[0].request
        assert b"is_stale" in request.content


class TestAsyncCloudAdapter:
    """Tests for async AsyncCloudAdapter with mocked responses."""

    @respx.mock
    async def test_get_returns_entry(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test getting a cached entry."""
        respx.get("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": {"id": "456"},
                    "tags": [["post", "456"]],
                    "created_at": 2000,
                    "expires_at": 3000,
                    "grace_until": 4000,
                },
            )
        )

        result = await async_cloud_adapter.get("key1")
        assert result is not None
        assert result.value == {"id": "456"}
        assert result.grace_until == 4000

    @respx.mock
    async def test_get_returns_none_on_404(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test that 404 returns None."""
        respx.get("https://api.test.dev/cache/test/nonexistent").mock(
            return_value=httpx.Response(404)
        )

        result = await async_cloud_adapter.get("nonexistent")
        assert result is None

    @respx.mock
    async def test_set_sends_entry(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test setting a cached entry."""
        route = respx.put("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(200)
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
    async def test_delete_sends_request(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test deleting a cached entry."""
        route = respx.delete("https://api.test.dev/cache/test/key1").mock(
            return_value=httpx.Response(200)
        )

        await async_cloud_adapter.delete("key1")
        assert route.called

    @respx.mock
    async def test_get_tag_invalidation_time(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test getting tag invalidation time."""
        respx.get("https://api.test.dev/tags/test/post:456").mock(
            return_value=httpx.Response(200, json={"timestamp": 3000})
        )

        result = await async_cloud_adapter.get_tag_invalidation_time(
            Tag(("post", "456"))
        )
        assert result == 3000

    @respx.mock
    async def test_set_tag_invalidation_time(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test setting tag invalidation time."""
        route = respx.put("https://api.test.dev/tags/test/post:456").mock(
            return_value=httpx.Response(200)
        )

        await async_cloud_adapter.set_tag_invalidation_time(Tag(("post", "456")), 4000)
        assert route.called

    @respx.mock
    async def test_clear_sends_request(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test clearing all cached entries."""
        route = respx.delete("https://api.test.dev/cache/test").mock(
            return_value=httpx.Response(200)
        )

        await async_cloud_adapter.clear()
        assert route.called

    @respx.mock
    async def test_report_verification(
        self, async_cloud_adapter: AsyncCloudAdapter
    ) -> None:
        """Test reporting verification result."""
        route = respx.post("https://api.test.dev/verify").mock(
            return_value=httpx.Response(200)
        )

        await async_cloud_adapter.report_verification(
            key="key1",
            is_stale=False,
            cached_hash="abc123",
            fresh_hash="abc123",
        )

        assert route.called
