# QueryCache: Python Implementation & Documentation

**Status:** Design complete — ready for implementation

**Date:** 2026-01-30

**Worktree:** `.worktrees/maximalist-types-spike`

---

## Overview

This design covers three deliverables:

1. **Python QueryCache implementation** — Port primitives + QueryCache using spike32's Pythonic pattern
2. **Documentation update** — 4 tabs: TS Basic, TS QueryCache, Python Basic, Python QueryCache
3. **Marketing page update** — Same 4 tabs on homepage

Each deliverable is a separate PR.

---

## Part 1: TypeScript Reference (Complete)

The TS implementation at `.worktrees/maximalist-types-spike/packages/core` is the source of truth for **behavior**. Python achieves the same guarantees with Pythonic syntax.

### TS API Summary

**Primitives** (`createPrimitives()`):
```typescript
const cache = createPrimitives({ adapter, prefix, defaultTtl, defaultGrace });

await cache.query({ key, tags, fn, ttl, grace });  // Stampede protection, SWR, verification
await cache.get(key);                               // Raw get (escape hatch)
await cache.set(key, value, { tags, ttl, grace }); // Raw set (escape hatch)
await cache.del(key);                               // Raw delete (escape hatch)
await cache.invalidate(tags, exact?);               // Tag-based invalidation
await cache.clear();
await cache.disconnect();
```

**QueryCache** (`QueryCache()`):
```typescript
const cache = QueryCache({
  schema: at('posts', () => wild(() => at('comments', () => wild))),
  adapter: new MemoryAdapter(),
  queries: (tags) => ({
    getPost: (postId: string) => ({
      tags: [tags.posts(postId)],
      fn: () => fetchPost(postId),
    }),
    getComments: (postId: string) => ({
      tags: [tags.posts(postId).comments],
      fn: () => fetchComments(postId),
    }),
  }),
});

const post = await cache.getPost('123');
await cache.invalidate(cache.tags.posts('123'));  // Hierarchical
await cache.primitives.get('manual-key');         // Escape hatch
```

**Schema builders**: `at(name, child?)`, `wild` (dual-nature: value and callable)

---

## Part 2: Python Implementation

### Design Criteria (10/10 achieved in spike32)

| # | Criterion | How |
|---|-----------|-----|
| 1 | Pythonic | Classes + annotations, not function builders |
| 2 | Named queries with valid tags | `@cached(Schema.path())` decorator |
| 3 | Queries must have tags | Decorator requires specs |
| 4 | Invalid tags rejected | Mypy catches at type-check time |
| 5 | Queries typed at call site | `async def -> T`, mypy confirms |
| 6 | Unique cache keys | Method names unique per class |
| 7 | Same args for tags and fn | Wild count == param count, validated at class creation |
| 8 | Typed invalidation | `invalidate(TypedTag)` |
| 9 | IDE autocomplete works | Schema attributes are real |
| 10 | Async-native | `async def` everywhere |

### Python vs TypeScript Syntax

| Concept | TypeScript | Python |
|---------|------------|--------|
| Schema definition | `at('posts', () => wild)` | `class Tags(TagSchema): posts: Wild[Children]` |
| Wild segment | `wild` (function) | `Wild[T]` (generic annotation) |
| Static segment | `.at('settings')` sibling | `settings: Static` annotation |
| QueryCache | `QueryCache({ schema, queries })` | `class MyCache(QueryCache[Tags])` |
| Query definition | `queries: (tags) => ({ name: ... })` | `@cached(Tags.path()) async def name()` |
| Primitives access | `cache.primitives.get()` | `cache.primitives.get()` |

The syntax differs, but the **type guarantees are equivalent**:
- Invalid tag paths caught at type-check time
- Wild count must match parameter count
- Hierarchical invalidation works the same way

### Architecture

```
TagSchema (annotation-based schema definition)
├── Wild[ChildrenT]     ← parameterized tag (adds wild on call)
├── Static              ← leaf tag (no wild)
└── Descriptors         ← class access → TagSpec, instance access → WildNode

QueryCache[SchemaT] (typed query cache)
├── @cached(*specs)     ← decorator with tag specs from schema CLASS
├── .t property         ← schema INSTANCE for runtime tag construction
├── .primitives         ← escape hatch to raw operations
└── .invalidate()       ← accepts TypedTag

Primitives (axiomatic layer)
├── query()             ← stampede protection, SWR, verification
├── get(), set(), del() ← raw escape hatches
├── invalidate()        ← tag-based invalidation
└── clear(), disconnect()
```

### Full Example

```python
from t87s import (
    QueryCache, cached, TagSchema, Wild, Static, TypedTag,
    create_primitives, MemoryAdapter,
)

# 1. Define schema (pure annotations)
class CommentsChildren(TagSchema):
    pass

class PostsChildren(TagSchema):
    comments: Wild[CommentsChildren]
    settings: Static

class CacheTags(TagSchema):
    posts: Wild[PostsChildren]
    users: Wild[TagSchema]
    config: Static

# 2. Define queries with @cached decorator
class MyCache(QueryCache[CacheTags]):

    @cached(CacheTags.users())  # 1 wild = 1 param
    async def get_user(self, id: str) -> User:
        return await fetch_user(id)

    @cached(CacheTags.posts().comments())  # 2 wilds = 2 params
    async def get_comment(self, post_id: str, comment_id: str) -> Comment:
        return await fetch_comment(post_id, comment_id)

    @cached(CacheTags.config)  # Static tag, 0 params
    async def get_config(self) -> dict[str, Any]:
        return {"theme": "dark"}

# 3. Use
cache = MyCache(adapter=MemoryAdapter())
user = await cache.get_user("123")
comment = await cache.get_comment("post-1", "comment-1")

# 4. Invalidate
await cache.invalidate(cache.t.posts("123"))  # Hierarchical: nukes post + comments
await cache.invalidate(cache.t.posts("123").comments("456"))  # Specific comment

# 5. Escape hatch
await cache.primitives.set("manual-key", data, tags=[("custom",)], ttl="1h")
result = await cache.primitives.get("manual-key")
```

### The Typing Trick

```python
if TYPE_CHECKING:
    Wild = WildTagSpec  # Mypy sees Wild[T] as WildTagSpec[T]
else:
    Wild = _WildMarker  # Runtime marker for descriptor setup
```

This makes mypy understand that `CacheTags.posts()` returns something with `PostsChildren`'s attributes.

---

## Implementation Tasks

### Task 1: Types & Duration

**Files:** `src/t87s/types.py`, `src/t87s/duration.py`

```python
# types.py
from dataclasses import dataclass
from typing import Protocol, TypeVar, Generic

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class CacheEntry(Generic[T]):
    value: T
    tags: list[tuple[str, ...]]
    created_at: int      # Unix timestamp ms
    expires_at: int      # TTL expiration
    grace_until: int | None  # Grace period expiration

# duration.py
def parse_duration(duration: str | int) -> int:
    """Parse '5m', '1h', '30s' to milliseconds. Passthrough int."""
```

### Task 2: Storage Adapter Protocol

**File:** `src/t87s/adapters/base.py`

```python
from typing import Protocol

class StorageAdapter(Protocol):
    async def get(self, key: str) -> CacheEntry | None: ...
    async def set(self, key: str, entry: CacheEntry) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def get_tag_invalidation_time(self, tag: tuple[str, ...]) -> int | None: ...
    async def set_tag_invalidation_time(self, tag: tuple[str, ...], time: int) -> None: ...
    async def clear(self) -> None: ...
    async def disconnect(self) -> None: ...

class VerifiableAdapter(Protocol):
    """Optional mixin for adapters that support staleness verification."""
    async def report_verification(
        self, key: str, is_stale: bool, cached_hash: str, fresh_hash: str
    ) -> None: ...
```

### Task 3: Memory Adapter

**File:** `src/t87s/adapters/memory.py`

Port from TS `memory.ts`. Use `OrderedDict` for LRU, `asyncio.Lock` for thread safety.

### Task 4: Primitives

**File:** `src/t87s/primitives.py`

Port from TS `primitives.ts`:
- `query()` with stampede protection (`asyncio.Lock`, in-flight tracking)
- `get()`, `set()`, `del()` escape hatches
- `invalidate()` with hierarchical tag matching (check all prefixes)
- TTL/grace handling
- Verification sampling

### Task 5: Tag Schema System

**File:** `src/t87s/schema.py`

Extract from spike32:
- `TagSchema` base class with `__init_subclass__` magic
- `Wild[T]`, `Static` type markers
- `WildTagSpec`, `StaticTagSpec` for mypy
- `WildDescriptor`, `StaticDescriptor` for runtime
- `TagSpec` for path building
- `TypedTag` dataclass

### Task 6: QueryCache Class

**File:** `src/t87s/query_cache.py`

Extract from spike32:
- `QueryCache[SchemaT]` generic base class
- `@cached(*specs)` decorator
- `.t` property for runtime tag construction
- `.primitives` property for escape hatch
- `.invalidate()` method
- Wild count validation at class creation time

### Task 7: Package Exports

**File:** `src/t87s/__init__.py`

```python
# Primitives
from t87s.primitives import create_primitives, Primitives

# QueryCache
from t87s.query_cache import QueryCache, cached
from t87s.schema import TagSchema, Wild, Static, TypedTag

# Adapters
from t87s.adapters import MemoryAdapter

# Types
from t87s.types import CacheEntry, Duration
from t87s.duration import parse_duration

__all__ = [
    # Primitives
    "create_primitives", "Primitives",
    # QueryCache
    "QueryCache", "cached", "TagSchema", "Wild", "Static", "TypedTag",
    # Adapters
    "MemoryAdapter",
    # Types
    "CacheEntry", "Duration", "parse_duration",
]
```

### Task 8: Tests

**Files:** `tests/test_primitives.py`, `tests/test_query_cache.py`, `tests/test_schema.py`

Port test cases from TS:
- Stampede protection (concurrent requests share promise)
- TTL expiration
- Grace period / SWR
- Hierarchical invalidation
- Exact invalidation mode
- Type safety (mypy should catch invalid paths)

### Task 9: Linting & Formatting Setup

**Files:** `pyproject.toml`, `ruff.toml` (if needed)

Ensure tooling is configured:

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.10"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Run before every commit:
```bash
ruff check src tests --fix
ruff format src tests
mypy src
pytest
```

---

## Part 3: Documentation Update

**Location:** `packages/core/docs/src/content/docs/`

### Changes

1. **getting-started.mdx** — Add QueryCache examples, expand to 4 code variants
2. **api/reference.mdx** — Document both Primitives and QueryCache APIs
3. **New: api/primitives.mdx** — Dedicated primitives reference
4. **New: api/query-cache.mdx** — Dedicated QueryCache reference

### Tab Structure

Each code example should have 4 tabs:

```mdx
<Tabs>
  <TabItem label="TS Basic">
    ```typescript
    const cache = createPrimitives({ adapter });
    await cache.query({ key, tags, fn });
    ```
  </TabItem>
  <TabItem label="TS QueryCache">
    ```typescript
    const cache = QueryCache({ schema: at('posts', () => wild), ... });
    await cache.getPost('123');
    ```
  </TabItem>
  <TabItem label="Python Basic">
    ```python
    cache = create_primitives(adapter=MemoryAdapter())
    await cache.query(key=..., tags=..., fn=...)
    ```
  </TabItem>
  <TabItem label="Python QueryCache">
    ```python
    class MyCache(QueryCache[Tags]):
        @cached(Tags.posts())
        async def get_post(self, id: str) -> Post: ...
    ```
  </TabItem>
</Tabs>
```

---

## Part 4: Marketing Page Update

**Location:** `packages/web/src/app/page.tsx`

### Current State

2 tabs: TypeScript, Python (both showing old `defineTags`/`T87s` API)

### Target State

4 tabs:
1. **TS Basic** — `createPrimitives()` example
2. **TS QueryCache** — `QueryCache()` with `at`/`wild` schema
3. **Python Basic** — `create_primitives()` example
4. **Python QueryCache** — `QueryCache[Tags]` with `@cached` decorator

### Code Examples

```typescript
// TS Basic
const cache = createPrimitives({
  adapter: new CloudAdapter({ apiKey: 't87s_...' }),
});

const user = await cache.query({
  key: `user:${id}`,
  tags: [['users', id]],
  fn: () => db.users.findById(id),
});

await cache.invalidate([['users', id]]);
```

```typescript
// TS QueryCache
const cache = QueryCache({
  schema: at('users', () => wild).at('posts', () => wild),
  adapter: new CloudAdapter({ apiKey: 't87s_...' }),
  queries: (tags) => ({
    getUser: (id: string) => ({
      tags: [tags.users(id)],
      fn: () => db.users.findById(id),
    }),
  }),
});

const user = await cache.getUser('123');
await cache.invalidate(cache.tags.users('123'));
```

```python
# Python Basic
cache = create_primitives(
    adapter=CloudAdapter(api_key="t87s_...")
)

user = await cache.query(
    key=f"user:{id}",
    tags=[("users", id)],
    fn=lambda: db.users.find_by_id(id),
)

await cache.invalidate([("users", id)])
```

```python
# Python QueryCache
class UserTags(TagSchema):
    users: Wild[TagSchema]
    posts: Wild[TagSchema]

class MyCache(QueryCache[UserTags]):
    @cached(UserTags.users())
    async def get_user(self, id: str) -> User:
        return await db.users.find_by_id(id)

cache = MyCache(adapter=CloudAdapter(api_key="t87s_..."))
user = await cache.get_user("123")
await cache.invalidate(cache.t.users("123"))
```

---

## PR Structure

### PR 1: Python Implementation

**Branch:** `feat/python-query-cache`

**Scope:**
- `packages/python/src/t87s/` — Full implementation
- `packages/python/tests/` — Test suite
- `packages/python/pyproject.toml` — Dependencies

**Before PR:**
```bash
cd packages/python && source .venv/bin/activate
ruff check src tests --fix && ruff format src tests
mypy src && pytest
```

**Merge target:** `maximalist-types-spike` branch first, then main

### PR 2: Documentation Update

**Branch:** `docs/query-cache-api`

**Scope:**
- `packages/core/docs/src/content/docs/` — Updated MDX files

**Before PR:**
```bash
cd packages/core/docs && pnpm build  # Verify docs build
```

**Depends on:** PR 1 merged (so Python examples are accurate)

### PR 3: Marketing Page Update

**Branch:** `feat/marketing-4-tabs`

**Scope:**
- `packages/web/src/app/page.tsx` — 4-tab code block

**Before PR:**
```bash
cd packages/web
pnpm lint && pnpm format
pnpm build  # Verify build succeeds
```

**Depends on:** PR 1 merged

---

## Pre-Implementation Checklist

Before starting:

1. [ ] Merge main into `maximalist-types-spike` worktree
2. [ ] Update Python submodule if behind
3. [ ] Verify TS tests pass in worktree: `pnpm test` in `packages/core`

---

## Quality Gates

All PRs must pass linting and formatting before merge.

### TypeScript (`packages/core`)

```bash
pnpm lint          # ESLint
pnpm format        # Prettier (check)
pnpm format:fix    # Prettier (fix)
pnpm typecheck     # tsc --noEmit
pnpm test          # Vitest
```

### Python (`packages/python`)

```bash
# All commands use .venv
source .venv/bin/activate

ruff check src tests           # Linting
ruff format src tests          # Formatting (check)
ruff format --fix src tests    # Formatting (fix)
mypy src                       # Type checking (strict)
pytest                         # Tests
```

### CI Requirements

Each PR must pass:
- [ ] Linting (no errors)
- [ ] Formatting (no changes needed)
- [ ] Type checking (no errors)
- [ ] Tests (all pass)

---

## References

| Resource | Location |
|----------|----------|
| Golden spike (Python) | `packages/python/src/t87s/query_cache_spike32.py` |
| TS primitives | `.worktrees/maximalist-types-spike/packages/core/src/primitives.ts` |
| TS QueryCache | `.worktrees/maximalist-types-spike/packages/core/src/query-cache.ts` |
| TS schema builders | `.worktrees/maximalist-types-spike/packages/core/src/schema.ts` |
| Current docs | `packages/core/docs/src/content/docs/` |
| Marketing page | `packages/web/src/app/page.tsx` |

---

## Decisions Log

| Question | Decision | Rationale |
|----------|----------|-----------|
| Python schema syntax | Class-based `TagSchema` with annotations | Pythonic, full mypy support |
| Sync vs async | Async-only | Modern Python, matches real-world use |
| Two-class vs single-class | Single-class | Spike17 (two-class) was clunky |
| How to express wilds | `()` calls mark wild positions | `posts()` = 1 wild, intuitive |
| Primitives API | Match TS exactly | Consistent cross-language behavior |
