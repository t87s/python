"""Shared pytest fixtures."""

import pytest

from t87s import AsyncMemoryAdapter


@pytest.fixture
def async_adapter() -> AsyncMemoryAdapter:
    """Create a fresh AsyncMemoryAdapter for each test."""
    return AsyncMemoryAdapter()
