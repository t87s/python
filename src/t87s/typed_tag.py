"""TypedTag for type-safe cache invalidation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TypedTag:
    """A type-safe tag for cache invalidation."""

    path: tuple[str, ...]

    def __repr__(self) -> str:
        return f"Tag({'/'.join(self.path)})"
