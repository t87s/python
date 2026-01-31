"""Tests for TypedTag."""

from t87s.typed_tag import TypedTag


class TestTypedTag:
    def test_create_from_tuple(self) -> None:
        tag = TypedTag(("users", "123"))
        assert tag.path == ("users", "123")

    def test_repr(self) -> None:
        tag = TypedTag(("users", "123", "posts"))
        assert repr(tag) == "Tag(users/123/posts)"

    def test_frozen(self) -> None:
        tag = TypedTag(("users",))
        # Should raise FrozenInstanceError
        import dataclasses

        import pytest

        with pytest.raises(dataclasses.FrozenInstanceError):
            tag.path = ("other",)  # type: ignore

    def test_hashable(self) -> None:
        tag1 = TypedTag(("users", "123"))
        tag2 = TypedTag(("users", "123"))
        assert hash(tag1) == hash(tag2)
        assert {tag1, tag2} == {tag1}
