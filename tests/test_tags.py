"""Tests for tag utilities."""

from t87s import (
    Tag,
    define_tags,
    deserialize_tag,
    is_tag_prefix,
    serialize_tag,
)


class TestDefineTags:
    """Tests for define_tags function."""

    def test_simple_tag(self) -> None:
        """Test defining a simple tag."""
        tags = define_tags({"user": lambda id: ("user", id)})
        result = tags["user"]("123")
        assert result == ("user", "123")

    def test_nested_tag(self) -> None:
        """Test defining a nested tag."""
        tags = define_tags({"user_posts": lambda user_id: ("user", user_id, "posts")})
        result = tags["user_posts"]("456")
        assert result == ("user", "456", "posts")

    def test_multiple_tags(self) -> None:
        """Test defining multiple tags."""
        tags = define_tags(
            {
                "user": lambda id: ("user", id),
                "post": lambda id: ("post", id),
            }
        )
        assert tags["user"]("1") == ("user", "1")
        assert tags["post"]("2") == ("post", "2")

    def test_tag_is_tuple(self) -> None:
        """Test that tags are tuples."""
        tags = define_tags({"user": lambda id: ("user", id)})
        result = tags["user"]("123")
        assert isinstance(result, tuple)


class TestSerializeTag:
    """Tests for serialize_tag function."""

    def test_simple_tag(self) -> None:
        """Test serializing a simple tag."""
        tag = Tag(("user", "123"))
        assert serialize_tag(tag) == "user:123"

    def test_nested_tag(self) -> None:
        """Test serializing a nested tag."""
        tag = Tag(("user", "123", "posts"))
        assert serialize_tag(tag) == "user:123:posts"

    def test_single_part(self) -> None:
        """Test serializing a single-part tag."""
        tag = Tag(("user",))
        assert serialize_tag(tag) == "user"

    def test_escape_colon(self) -> None:
        """Test escaping colons in tag parts."""
        tag = Tag(("key:with:colons", "value"))
        serialized = serialize_tag(tag)
        assert "\\:" in serialized

    def test_escape_backslash(self) -> None:
        """Test escaping backslashes in tag parts."""
        tag = Tag(("key\\with\\backslash", "value"))
        serialized = serialize_tag(tag)
        assert "\\\\" in serialized


class TestDeserializeTag:
    """Tests for deserialize_tag function."""

    def test_simple_tag(self) -> None:
        """Test deserializing a simple tag."""
        result = deserialize_tag("user:123")
        assert result == ("user", "123")

    def test_nested_tag(self) -> None:
        """Test deserializing a nested tag."""
        result = deserialize_tag("user:123:posts")
        assert result == ("user", "123", "posts")

    def test_single_part(self) -> None:
        """Test deserializing a single-part tag."""
        result = deserialize_tag("user")
        assert result == ("user",)

    def test_roundtrip_with_colon(self) -> None:
        """Test that serialization/deserialization roundtrips with colons."""
        original = Tag(("key:with:colons", "value"))
        serialized = serialize_tag(original)
        deserialized = deserialize_tag(serialized)
        assert deserialized == original

    def test_roundtrip_with_backslash(self) -> None:
        """Test that serialization/deserialization roundtrips with backslashes."""
        original = Tag(("key\\with\\backslash", "value"))
        serialized = serialize_tag(original)
        deserialized = deserialize_tag(serialized)
        assert deserialized == original


class TestIsTagPrefix:
    """Tests for is_tag_prefix function."""

    def test_exact_match(self) -> None:
        """Test that exact matches return True."""
        parent = Tag(("user", "123"))
        child = Tag(("user", "123"))
        assert is_tag_prefix(parent, child) is True

    def test_prefix_match(self) -> None:
        """Test that prefixes match."""
        parent = Tag(("user", "123"))
        child = Tag(("user", "123", "posts"))
        assert is_tag_prefix(parent, child) is True

    def test_single_part_prefix(self) -> None:
        """Test that single-part prefixes match."""
        parent = Tag(("user",))
        child = Tag(("user", "123", "posts"))
        assert is_tag_prefix(parent, child) is True

    def test_not_prefix_different_values(self) -> None:
        """Test that different values don't match."""
        parent = Tag(("user", "123"))
        child = Tag(("user", "456"))
        assert is_tag_prefix(parent, child) is False

    def test_not_prefix_longer_parent(self) -> None:
        """Test that longer parent doesn't match shorter child."""
        parent = Tag(("user", "123", "posts"))
        child = Tag(("user", "123"))
        assert is_tag_prefix(parent, child) is False

    def test_not_prefix_different_tag(self) -> None:
        """Test that completely different tags don't match."""
        parent = Tag(("user", "123"))
        child = Tag(("post", "456"))
        assert is_tag_prefix(parent, child) is False
