# t87s

Declarative cache invalidation for Python.

## Install

```bash
pip install t87s              # Core + MemoryAdapter
pip install t87s[redis]       # + Redis support
pip install t87s[all]         # Everything
```

## Quickstart

```python
from t87s import QueryCache, TagSchema, Wild, AsyncMemoryAdapter, cached

class MyTags(TagSchema):
    users: Wild[TagSchema]

class MyCache(QueryCache[MyTags]):
    @cached(MyTags.users())
    async def get_user(self, id: str) -> dict:
        return await db.users.find_by_id(id)

cache = MyCache(adapter=AsyncMemoryAdapter())

# Cache miss, fetches from DB
user = await cache.get_user("123")

# Cache hit, instant
again = await cache.get_user("123")

# Invalidate when data changes
await cache.invalidate(cache.t.users("123"))

# Cache miss again, refetches
fresh = await cache.get_user("123")
```

## Docs

Full documentation: https://docs.t87s.dev
