# QueryCache Python Design

**Goal:** Port the TypeScript QueryCache API to Python with full type safety and Pythonic syntax.

**Reference:** TypeScript implementation at `/.worktrees/maximalist-types-spike/packages/core`

---

## Design Criteria

1. **Pythonic** - Classes, inheritance, decorators (no lambdas in decorators)
2. **Named queries associated with valid tags** - Inheritance enforces
3. **Queries must have tags** - Parent method required
4. **Invalid tags rejected** - Schema type system
5. **Queries typed at call site** - `async def -> T`, mypy confirms
6. **Unique cache keys** - Method names unique per class
7. **Same args for tags and fn** - Inheritance enforces same signature (LSP)
8. **Typed invalidation** - `invalidate(TypedTag)`
9. **IDE autocomplete works** - Real methods on real classes
10. **Async-native** - `async def` everywhere

---

## Part 1: Tag Schema System (COMPLETED)

Pure annotation syntax with full mypy support:

```python
class PostsChildren(TagSchema):
    comments: Wild[CommentsChildren]
    settings: Static

class CacheTags(TagSchema):
    posts: Wild[PostsChildren]
    users: Wild[TagSchema]
    global_: Static
```

**No `= Wild()`, no `= Static()`, just annotations.**

### How It Works

1. `Wild` inherits from `Generic[ChildrenT]` → mypy sees it as a generic type
2. `Wild` defines stub methods → mypy sees `Wild[T]` as callable with `.path`
3. `TagSchema.__init_subclass__` reads annotations → creates descriptors at class definition
4. Lazy resolution via `get_type_hints()` → handles forward references

### Files

- `src/t87s/query_cache_spike12.py` - Working implementation

---

## Part 2: QueryCache API (NEW - Inheritance Pattern)

### The Pattern

```python
from t87s import QueryCache, Tagger, cached, Wild, Static, TagSchema

# 1. Define schema (pure annotations)
class PostsChildren(TagSchema):
    comments: Wild[TagSchema]
    settings: Static

class CacheTags(TagSchema):
    posts: Wild[PostsChildren]
    users: Wild[TagSchema]

# 2. Define tags (what tags each query uses)
class MyTags(Tagger[CacheTags]):
    def get_post(self, post_id: str) -> Awaitable[Post]:
        return self.returns([self.t.posts(post_id)])

    def get_user(self, user_id: str) -> Awaitable[User]:
        return self.returns([self.t.users(user_id)])

    def get_comments(self, post_id: str) -> Awaitable[list[Comment]]:
        return self.returns([self.t.posts(post_id).comments])

# 3. Implement queries (inherits from tags)
class MyCache(QueryCache[MyTags], MyTags):
    @cached
    async def get_post(self, post_id: str) -> Post:
        return await fetch_post(post_id)

    @cached
    async def get_user(self, user_id: str) -> User:
        return await fetch_user(user_id)

    @cached
    async def get_comments(self, post_id: str) -> list[Comment]:
        return await fetch_comments(post_id)

# 4. Use
cache = MyCache(adapter=MemoryAdapter())
post = await cache.get_post("123")
await cache.invalidate(cache.t.posts("123"))
```

### Why Inheritance?

- **Same signature enforced**: Mypy catches LSP violations if child has different args
- **Call-site typing**: `await cache.get_post("123")` returns `Post`
- **Real methods**: IDE autocomplete works perfectly
- **Tags required**: `@cached` decorator calls parent to get tags; fails if missing

### Architecture

```
Primitives (axiomatic layer)
├── query()      ← stampede protection, SWR, verification
├── get()        ← raw escape hatch
├── set()        ← raw escape hatch
├── del()        ← raw escape hatch
├── invalidate()
├── clear()
└── disconnect()

QueryCache (typed layer, built on Primitives)
├── Tagger[Schema] base class (defines tags)
├── @cached decorator (wires tags to queries)
└── inherits from Tagger (enforces signatures)
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `TagSchema` | Base for schema definitions (auto-creates descriptors) |
| `Wild[T]` | Type marker for parameterized tags |
| `Static` | Type marker for leaf tags |
| `Tagger[Schema]` | Base for tag definitions |
| `QueryCache[Tagger]` | Base for query implementations |
| `@cached` | Decorator that adds caching to query methods |

---

## Part 3: Implementation Plan

### Task 1: Primitives
Port `primitives.ts` → `primitives.py`
- `query()` with stampede protection (asyncio locks)
- `get()`, `set()`, `del()` escape hatches
- `invalidate()` with hierarchical tag matching
- TTL/grace handling

### Task 2: Storage Adapter Protocol
```python
class StorageAdapter(Protocol):
    async def get(self, key: str) -> CacheEntry | None: ...
    async def set(self, key: str, entry: CacheEntry) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def get_tag_invalidation_time(self, tag: tuple[str, ...]) -> int | None: ...
    async def set_tag_invalidation_time(self, tag: tuple[str, ...], time: int) -> None: ...
    async def clear(self) -> None: ...
    async def disconnect(self) -> None: ...
```

### Task 3: Memory Adapter
Port `memory.ts` → `memory_adapter.py`

### Task 4: Tagger Base Class
```python
class Tagger(Generic[SchemaT]):
    t: SchemaT
    def returns(self, tags: list[TypedTag]) -> _TagCollector[Any]: ...
```

### Task 5: QueryCache Base Class
```python
class QueryCache(Generic[TaggerT]):
    def _get_tags_for(self, method_name: str, *args, **kwargs) -> list[TypedTag]: ...
    async def invalidate(self, *tags: TypedTag) -> None: ...
```

### Task 6: @cached Decorator
```python
def cached(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Wraps method to get tags from parent and add caching."""
    ...
```

### Task 7: Type Definitions
```python
@dataclass
class CacheEntry(Generic[T]):
    value: T
    tags: list[tuple[str, ...]]
    created_at: int
    expires_at: int
    grace_until: int | None

@dataclass(frozen=True)
class TypedTag:
    path: tuple[str, ...]
```

### Task 8: Integration Tests
Port `query-cache.integration.test.ts` → pytest

### Task 9: Package Exports
Update `__init__.py`

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Decorator vs fluent vs inheritance? | **Inheritance** - enforces signatures, typed call sites |
| Sync vs async? | **Async-only** - modern Python, matches use case |
| Lambda in decorators? | **No** - unpythonic, use inheritance instead |
| How to associate tags with queries? | **Parent class methods** - same signature, called by @cached |

---

## Files

- Spike 12: `src/t87s/query_cache_spike12.py` - Tag schema system
- Spike 17: `/tmp/spike17.py` - Full inheritance pattern (reference)

---

## References

- TypeScript implementation: `/.worktrees/maximalist-types-spike/packages/core/`
- TypeScript Primitives: `primitives.ts` (query with stampede/SWR/verification)
- TypeScript QueryCache: `query-cache.ts` (typed layer)
