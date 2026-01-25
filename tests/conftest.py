"""Shared pytest fixtures."""

import pytest

from t87s import AsyncMemoryAdapter, MemoryAdapter, define_tags


@pytest.fixture
def adapter() -> MemoryAdapter:
    """Create a fresh MemoryAdapter for each test."""
    return MemoryAdapter()


@pytest.fixture
def async_adapter() -> AsyncMemoryAdapter:
    """Create a fresh AsyncMemoryAdapter for each test."""
    return AsyncMemoryAdapter()


@pytest.fixture
def tags() -> dict:
    """Create common tag definitions for tests."""
    return define_tags(
        {
            "user": lambda id: ("user", id),
            "post": lambda id: ("post", id),
            "user_posts": lambda user_id: ("user", user_id, "posts"),
        }
    )
