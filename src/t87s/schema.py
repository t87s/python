"""TagSchema system for type-safe cache tags.

This module provides:
- TagSchema: Base class for defining tag schemas
- Wild[T]: Annotation for parameterized (wild) tag segments
- Static: Annotation for leaf (static) tag segments
- Descriptors that enable dual behavior:
  - Class access: Returns specs for @cached decorator
  - Instance access: Returns nodes for runtime tag construction
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from t87s.typed_tag import TypedTag

ChildrenT = TypeVar("ChildrenT", bound="TagSchema")

# =============================================================================
# Tag Spec (runtime) - used by @cached decorator
# =============================================================================


class TagSpec:
    """Represents a tag path pattern with wildcards."""

    __slots__ = ("_children_type", "_segments", "_wild_count")

    def __init__(
        self,
        segments: tuple[str, ...] = (),
        wild_count: int = 0,
        children_type: type[TagSchema] | None = None,
    ) -> None:
        self._segments = segments
        self._wild_count = wild_count
        self._children_type = children_type

    def __call__(self) -> TagSpec:
        """Add a wildcard segment."""
        return TagSpec(
            (*self._segments, "*"),
            self._wild_count + 1,
            self._children_type,
        )

    def __getattr__(self, name: str) -> TagSpec:
        if name.startswith("_"):
            raise AttributeError(name)

        children_type = None
        if self._children_type is not None:
            try:
                hints = get_type_hints(self._children_type)
                hint = hints.get(name)
                if hint:
                    origin = get_origin(hint)
                    if origin is not None and origin.__name__ in (
                        "Wild",
                        "_WildMarker",
                    ):
                        args = get_args(hint)
                        if args and isinstance(args[0], type):
                            children_type = args[0]
            except Exception:
                pass

        return TagSpec(
            (*self._segments, name),
            self._wild_count,
            children_type,
        )

    @property
    def wild_count(self) -> int:
        return self._wild_count

    @property
    def segments(self) -> tuple[str, ...]:
        return self._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        """Build a concrete path by filling wildcards with args."""
        result: list[str] = []
        arg_idx = 0
        for seg in self._segments:
            if seg == "*":
                result.append(str(args[arg_idx]))
                arg_idx += 1
            else:
                result.append(seg)
        return tuple(result)

    def __repr__(self) -> str:
        return f"TagSpec({'/'.join(self._segments)}, wilds={self._wild_count})"


# =============================================================================
# WildTagSpec / StaticTagSpec - what mypy sees
# =============================================================================


class WildTagSpec(Generic[ChildrenT]):
    """For mypy: represents a wild tag segment with children type."""

    __slots__ = ("_spec",)

    def __init__(self, spec: TagSpec) -> None:
        self._spec = spec

    if TYPE_CHECKING:

        def __call__(self) -> ChildrenT | WildTagSpec[ChildrenT]: ...
        def __getattr__(self, name: str) -> WildTagSpec[Any]: ...
    else:

        def __call__(self) -> TagSpec:
            return self._spec()

        def __getattr__(self, name: str) -> TagSpec:
            if name.startswith("_"):
                raise AttributeError(name)
            return getattr(self._spec, name)

    @property
    def wild_count(self) -> int:
        return self._spec._wild_count

    @property
    def segments(self) -> tuple[str, ...]:
        return self._spec._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        return self._spec.build_path(args)


class StaticTagSpec:
    """For mypy: represents a static (leaf) tag segment."""

    __slots__ = ("_spec",)

    def __init__(self, spec: TagSpec) -> None:
        self._spec = spec

    @property
    def wild_count(self) -> int:
        return 0

    @property
    def segments(self) -> tuple[str, ...]:
        return self._spec._segments

    def build_path(self, args: tuple[Any, ...]) -> tuple[str, ...]:
        return self._spec.build_path(args)


# =============================================================================
# WildNode - runtime tag construction
# =============================================================================


class WildNode(Generic[ChildrenT]):
    """Runtime node for building typed tags."""

    __slots__ = ("_children_type", "_path")

    def __init__(
        self, path: tuple[str, ...], children_type: type[ChildrenT] | None
    ) -> None:
        self._path = path
        self._children_type = children_type

    @property
    def path(self) -> tuple[str, ...]:
        return self._path

    def __call__(self, id: str) -> ChildrenT:
        """Add a value to the path and return children type."""
        new_path = (*self._path, id)
        if self._children_type is None:
            result = TagSchema.__new__(TagSchema)
            result._path = new_path
            return result  # type: ignore
        result = object.__new__(self._children_type)
        result._path = new_path
        return result


# =============================================================================
# THE KEY: Different Wild for mypy vs runtime
# =============================================================================

if TYPE_CHECKING:
    # For mypy: Wild[T] IS WildTagSpec[T]
    Wild = WildTagSpec
    Static = StaticTagSpec
else:
    # At runtime: Wild is just a marker class for descriptor recognition

    class _WildMarker(Generic[ChildrenT]):
        pass

    Wild = _WildMarker

    class _StaticMarker:
        pass

    Static = _StaticMarker


# =============================================================================
# Descriptors
# =============================================================================


class WildDescriptor(Generic[ChildrenT]):
    """Descriptor for wild tag segments."""

    __slots__ = ("_children_type", "_name")

    def __init__(self, children_type: type[ChildrenT] | None = None) -> None:
        self._name = ""
        self._children_type = children_type

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> WildTagSpec[ChildrenT]: ...

    @overload
    def __get__(self, obj: TagSchema, owner: type) -> WildNode[ChildrenT]: ...

    def __get__(
        self, obj: Any, owner: type
    ) -> WildTagSpec[ChildrenT] | WildNode[ChildrenT]:
        if obj is None:
            # Class access: return spec for @cached
            spec = TagSpec((self._name,), 0, self._children_type)
            return WildTagSpec(spec)
        else:
            # Instance access: return node for tag construction
            return WildNode((*obj._path, self._name), self._children_type)


class StaticDescriptor:
    """Descriptor for static (leaf) tag segments."""

    __slots__ = ("_name",)

    def __init__(self) -> None:
        self._name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> StaticTagSpec: ...

    @overload
    def __get__(self, obj: TagSchema, owner: type) -> TypedTag: ...

    def __get__(self, obj: Any, owner: type) -> StaticTagSpec | TypedTag:
        if obj is None:
            # Class access: return spec
            spec = TagSpec((self._name,), 0, None)
            return StaticTagSpec(spec)
        else:
            # Instance access: return typed tag
            return TypedTag((*obj._path, self._name))


# =============================================================================
# TagSchema Base
# =============================================================================


class TagSchema:
    """Base class for defining tag schemas.

    Subclass and add annotations to define your schema:

        class MyTags(TagSchema):
            users: Wild[TagSchema]
            posts: Wild[PostChildren]
            config: Static
    """

    __slots__ = ("_path",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        try:
            hints = get_type_hints(cls)
        except NameError:
            hints = {}

        raw_annotations = getattr(cls, "__annotations__", {})

        for name in set(hints.keys()) | set(raw_annotations.keys()):
            if name.startswith("_") or name in cls.__dict__:
                continue

            hint = hints.get(name)
            raw = raw_annotations.get(name)
            raw_str = str(raw) if raw and not isinstance(raw, str) else (raw or "")

            origin = get_origin(hint) if hint else None
            wild_names = ("Wild", "_WildMarker", "WildTagSpec")
            is_wild = (
                origin is not None and getattr(origin, "__name__", "") in wild_names
            ) or "Wild" in raw_str

            is_static = (
                hint is Static
                or raw_str == "Static"
                or getattr(hint, "__name__", "")
                in ("Static", "_StaticMarker", "StaticTagSpec")
            )

            if is_wild:
                children_type = None
                if origin is not None:
                    args = get_args(hint)
                    if args and isinstance(args[0], type):
                        children_type = args[0]

                desc: WildDescriptor[Any] = WildDescriptor(children_type)
                desc.__set_name__(cls, name)
                setattr(cls, name, desc)

            elif is_static:
                sdesc = StaticDescriptor()
                sdesc.__set_name__(cls, name)
                setattr(cls, name, sdesc)

    def __init__(self, path: tuple[str, ...] = ()) -> None:
        self._path = path

    @property
    def path(self) -> tuple[str, ...]:
        return self._path


__all__ = [
    "Static",
    "StaticTagSpec",
    "TagSchema",
    "TagSpec",
    "TypedTag",
    "Wild",
    "WildTagSpec",
]
