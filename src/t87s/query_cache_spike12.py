"""
Spike 12: Make Wild[T] preserve the type argument at runtime

Key insight: We need Wild[PostsChildren] to:
1. Be recognized by mypy as having .path and __call__
2. Preserve PostsChildren at runtime for get_type_hints()
3. Work as a descriptor OR be auto-converted to one

Strategy: Use typing._GenericAlias behavior but intercept in __init_subclass__
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

ChildrenT = TypeVar("ChildrenT", bound="TagSchema")


@dataclass(frozen=True, slots=True)
class TypedTag:
    path: tuple[str, ...]

    def __repr__(self) -> str:
        return f"Tag({'/'.join(self.path)})"


class WildNode(Generic[ChildrenT]):
    """Runtime callable tag node."""
    __slots__ = ("_path", "_children_type")

    def __init__(self, path: tuple[str, ...], children_type: type[ChildrenT] | None) -> None:
        self._path = path
        self._children_type = children_type

    @property
    def path(self) -> tuple[str, ...]:
        return self._path

    def __call__(self, id: str) -> ChildrenT:
        new_path = self._path + (id,)
        if self._children_type is None:
            return TagSchema(new_path)  # type: ignore[return-value]
        return self._children_type(new_path)

    def __repr__(self) -> str:
        return f"WildNode({'/'.join(self._path)}/*)"


class _WildDescriptor(Generic[ChildrenT]):
    """Internal descriptor."""
    __slots__ = ("_name", "_owner", "_children_type", "_resolved")

    def __init__(self, children_type: type[ChildrenT] | None = None) -> None:
        self._name = ""
        self._owner: type | None = None
        self._children_type = children_type
        self._resolved = children_type is not None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name
        self._owner = owner

    def _resolve(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        if self._owner is None:
            return
        try:
            hints = get_type_hints(self._owner)
            hint = hints.get(self._name)
            if hint:
                args = get_args(hint)
                if args:
                    child_type = args[0]
                    if isinstance(child_type, type) and issubclass(child_type, TagSchema):
                        self._children_type = child_type  # type: ignore[assignment]
        except Exception:
            pass

    def __get__(self, obj: Any, owner: type) -> Any:
        if obj is None:
            return self
        self._resolve()
        return WildNode(obj._path + (self._name,), self._children_type)


class _StaticDescriptor:
    """Internal descriptor for static nodes."""
    __slots__ = ("_name",)

    def __init__(self) -> None:
        self._name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, owner: type) -> Any:
        if obj is None:
            return self
        return TypedTag(obj._path + (self._name,))


# =============================================================================
# THE MAGIC: Wild inherits from Generic BUT we handle it specially
# =============================================================================

class Wild(Generic[ChildrenT]):
    """
    Type marker for wild tag nodes.

    For MYPY: Wild[T] is a generic type with .path and __call__
    For RUNTIME: __init_subclass__ converts annotations to descriptors
    """
    # These make mypy happy - it sees Wild[T] as having these
    @property
    def path(self) -> tuple[str, ...]:
        raise NotImplementedError("Wild is a type marker")

    def __call__(self, id: str) -> ChildrenT:
        raise NotImplementedError("Wild is a type marker")


class Static:
    """Type marker for static tag nodes."""
    @property
    def path(self) -> tuple[str, ...]:
        raise NotImplementedError("Static is a type marker")


class TagSchema:
    """Base class for tag schemas."""
    __slots__ = ("_path",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _setup_schema(cls)

    def __init__(self, path: tuple[str, ...] = ()) -> None:
        self._path = path

    @property
    def path(self) -> tuple[str, ...]:
        return self._path

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({'/'.join(self._path)})"


def _setup_schema(cls: type) -> None:
    """Auto-create descriptors from annotations."""
    try:
        hints = get_type_hints(cls)
    except NameError:
        # Forward reference not yet defined - use raw annotations
        hints = {}

    # Also check raw annotations for unresolved forward refs
    raw_annotations = getattr(cls, "__annotations__", {})

    for name in set(hints.keys()) | set(raw_annotations.keys()):
        if name.startswith("_"):
            continue
        if name in cls.__dict__:
            continue

        hint = hints.get(name)
        raw = raw_annotations.get(name)

        # Check if it's Wild[T]
        is_wild = False
        is_static = False

        if hint is not None:
            origin = get_origin(hint)
            if origin is Wild:
                is_wild = True
            elif hint is Static:
                is_static = True

        # Fallback to string matching for forward refs
        if not is_wild and not is_static and raw is not None:
            raw_str = str(raw) if not isinstance(raw, str) else raw
            if raw_str.startswith("Wild[") or raw_str == "Wild":
                is_wild = True
            elif raw_str == "Static":
                is_static = True

        if is_wild:
            wild_descriptor = _WildDescriptor[Any]()
            wild_descriptor.__set_name__(cls, name)
            setattr(cls, name, wild_descriptor)
        elif is_static:
            static_descriptor = _StaticDescriptor()
            static_descriptor.__set_name__(cls, name)
            setattr(cls, name, static_descriptor)


# =============================================================================
# TEST
# =============================================================================

print("=== Spike 12: Wild as Generic with protocol-like interface ===")
print()


class CommentsChildren(TagSchema):
    pass


class PostsChildren(TagSchema):
    comments: Wild[CommentsChildren]
    settings: Static


class CacheTags(TagSchema):
    posts: Wild[PostsChildren]
    users: Wild[TagSchema]
    global_: Static


tags = CacheTags()

print(f"tags.posts = {tags.posts}")
print(f"tags.posts('p1') = {tags.posts('p1')}")
print(f"tags.posts('p1').comments = {tags.posts('p1').comments}")
print(f"tags.posts('p1').comments('c1') = {tags.posts('p1').comments('c1')}")
print(f"tags.posts('p1').settings = {tags.posts('p1').settings}")
print(f"tags.users = {tags.users}")
print(f"tags.users('u1') = {tags.users('u1')}")
print(f"tags.global_ = {tags.global_}")
print()

# Verify paths
assert tags.posts.path == ("posts",)
assert tags.posts("p1").path == ("posts", "p1")
assert tags.posts("p1").comments.path == ("posts", "p1", "comments")
assert tags.posts("p1").comments("c1").path == ("posts", "p1", "comments", "c1")
assert tags.posts("p1").settings.path == ("posts", "p1", "settings")
assert tags.users.path == ("users",)
assert tags.users("u1").path == ("users", "u1")
assert tags.global_.path == ("global_",)
print("All paths correct!")
print()

print("""
Schema:
    class PostsChildren(TagSchema):
        comments: Wild[CommentsChildren]
        settings: Static

    class CacheTags(TagSchema):
        posts: Wild[PostsChildren]
        users: Wild[TagSchema]
        global_: Static

PURE ANNOTATIONS - no = Wild(), no = Static()!
""")
