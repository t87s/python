"""Tag definition and utilities."""

from collections.abc import Callable

from t87s.types import Tag

_ESCAPE_MAP = {"\\": "\\\\", ":": "\\:"}
_UNESCAPE_MAP = {"\\\\": "\\", "\\:": ":"}


def define_tags(
    definitions: dict[str, Callable[..., tuple[str, ...]]],
) -> dict[str, Callable[..., Tag]]:
    """
    Define all tags in a centralized location.
    Only way to produce Tag values.

    Example:
        tags = define_tags({
            "user": lambda id: ("user", id),
            "post": lambda id: ("post", id),
            "user_posts": lambda user_id: ("user", user_id, "posts"),
        })

        tags["user"]("123")       # Tag: ("user", "123")
        tags["user_posts"]("123") # Tag: ("user", "123", "posts")
    """
    result: dict[str, Callable[..., Tag]] = {}
    for name, fn in definitions.items():

        def make_tag(*args: str, _fn: Callable[..., tuple[str, ...]] = fn) -> Tag:
            parts = _fn(*args)
            return Tag(parts)

        result[name] = make_tag
    return result


def serialize_tag(tag: Tag) -> str:
    """Serialize tag tuple to string for storage keys."""

    def escape(part: str) -> str:
        result = part
        for char, escaped in _ESCAPE_MAP.items():
            result = result.replace(char, escaped)
        return result

    return ":".join(escape(str(p)) for p in tag)


def deserialize_tag(serialized: str) -> Tag:
    """Deserialize storage key back to tag tuple."""
    parts: list[str] = []
    current = ""
    i = 0

    while i < len(serialized):
        if serialized[i] == "\\":
            if i + 1 < len(serialized):
                escaped = serialized[i : i + 2]
                if escaped in _UNESCAPE_MAP:
                    current += _UNESCAPE_MAP[escaped]
                    i += 2
                    continue
            current += serialized[i]
            i += 1
        elif serialized[i] == ":":
            parts.append(current)
            current = ""
            i += 1
        else:
            current += serialized[i]
            i += 1

    parts.append(current)
    return Tag(tuple(parts))


def is_tag_prefix(parent: Tag, child: Tag) -> bool:
    """Check if parent is a prefix of child (for invalidation)."""
    if len(parent) > len(child):
        return False
    return child[: len(parent)] == parent
