"""Tests for TagSchema, Wild, Static system."""

from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag


class ChildTags(TagSchema):
    pass


class PostChildren(TagSchema):
    comments: Wild[ChildTags]
    settings: Static


class RootTags(TagSchema):
    posts: Wild[PostChildren]
    users: Wild[TagSchema]
    config: Static


class TestSchemaClassAccess:
    """Test class-level access (for @cached decorator specs)."""

    def test_wild_returns_spec(self) -> None:
        spec = RootTags.posts
        assert spec.segments == ("posts",)
        assert spec.wild_count == 0

    def test_wild_call_adds_wild(self) -> None:
        spec = RootTags.posts()
        assert spec.segments == ("posts", "*")
        assert spec.wild_count == 1

    def test_chained_access(self) -> None:
        spec = RootTags.posts().comments
        assert spec.segments == ("posts", "*", "comments")
        assert spec.wild_count == 1

    def test_chained_with_multiple_wilds(self) -> None:
        spec = RootTags.posts().comments()
        assert spec.segments == ("posts", "*", "comments", "*")
        assert spec.wild_count == 2

    def test_static_access(self) -> None:
        spec = RootTags.config
        assert spec.segments == ("config",)
        assert spec.wild_count == 0


class TestSchemaInstanceAccess:
    """Test instance-level access (for runtime tag construction)."""

    def test_wild_returns_node(self) -> None:
        root = RootTags()
        node = root.posts
        assert node.path == ("posts",)

    def test_wild_call_builds_tag_path(self) -> None:
        root = RootTags()
        child = root.posts("123")
        assert child.path == ("posts", "123")

    def test_chained_instance_access(self) -> None:
        root = RootTags()
        child = root.posts("p1").comments("c1")
        assert child.path == ("posts", "p1", "comments", "c1")

    def test_static_returns_typed_tag(self) -> None:
        root = RootTags()
        tag = root.config
        assert isinstance(tag, TypedTag)
        assert tag.path == ("config",)


class TestBuildPath:
    """Test building paths from specs."""

    def test_build_path_single_wild(self) -> None:
        spec = RootTags.posts()
        path = spec.build_path(("123",))
        assert path == ("posts", "123")

    def test_build_path_multiple_wilds(self) -> None:
        spec = RootTags.posts().comments()
        path = spec.build_path(("p1", "c1"))
        assert path == ("posts", "p1", "comments", "c1")

    def test_build_path_no_wilds(self) -> None:
        spec = RootTags.config
        path = spec.build_path(())
        assert path == ("config",)
