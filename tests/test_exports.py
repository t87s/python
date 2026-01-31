"""Tests for package exports."""


def test_new_exports_available() -> None:
    """Test that new QueryCache exports are available."""
    from t87s import (
        Primitives,
        QueryCache,
        Static,
        TagSchema,
        TypedTag,
        Wild,
        cached,
        create_primitives,
    )

    # Just verify they're importable
    assert Primitives is not None
    assert QueryCache is not None
    assert TagSchema is not None
    assert Wild is not None
    assert Static is not None
    assert TypedTag is not None
    assert cached is not None
    assert create_primitives is not None


def test_old_exports_still_work() -> None:
    """Test that old API exports still work."""
    from t87s import (
        AsyncMemoryAdapter,
        AsyncQueryConfig,
        AsyncT87s,
        MemoryAdapter,
        MutationResult,
        QueryConfig,
        T87s,
        define_tags,
    )

    # Just verify they're importable
    assert T87s is not None
    assert AsyncT87s is not None
    assert MemoryAdapter is not None
    assert AsyncMemoryAdapter is not None
    assert QueryConfig is not None
    assert AsyncQueryConfig is not None
    assert MutationResult is not None
    assert define_tags is not None
