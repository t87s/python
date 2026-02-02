"""QueryAwaitable - awaitable with .entries accessor for cache metadata."""

from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Generic,
    TypeVar,
)

from t87s.types import EntriesResult

T = TypeVar("T")


class QueryAwaitable(Generic[T]):
    """An awaitable that returns T, with an .entries property for cache metadata.

    Usage:
        result = await query_awaitable           # T
        entry = await query_awaitable.entries    # EntriesResult[T]
    """

    __slots__ = ("_value_fn", "_entries_fn")

    def __init__(
        self,
        value_fn: Callable[[], Coroutine[Any, Any, T]],
        entries_fn: Callable[[], Coroutine[Any, Any, EntriesResult[T]]],
    ) -> None:
        self._value_fn = value_fn
        self._entries_fn = entries_fn

    def __await__(self) -> Generator[Any, None, T]:
        return self._value_fn().__await__()

    @property
    def entries(self) -> Awaitable[EntriesResult[T]]:
        """Access cache metadata (before/after entries)."""
        return self._entries_fn()


__all__ = ["QueryAwaitable"]
