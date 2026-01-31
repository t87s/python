"""Tests for package exports."""


def test_core_exports_available() -> None:
    """Test that core exports are available."""
    from t87s import (
        AsyncMemoryAdapter,
        AsyncStorageAdapter,
        CacheEntry,
        Duration,
        Primitives,
        QueryCache,
        Static,
        Tag,
        TagSchema,
        TypedTag,
        Wild,
        cached,
        create_primitives,
        parse_duration,
    )

    # Verify they're importable
    assert AsyncMemoryAdapter is not None
    assert AsyncStorageAdapter is not None
    assert CacheEntry is not None
    assert Duration is not None
    assert Primitives is not None
    assert QueryCache is not None
    assert Static is not None
    assert Tag is not None
    assert TagSchema is not None
    assert TypedTag is not None
    assert Wild is not None
    assert cached is not None
    assert create_primitives is not None
    assert parse_duration is not None
