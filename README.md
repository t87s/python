# t87s

Declarative cache invalidation for Python.

## Install

```bash
pip install t87s              # Core + MemoryAdapter
pip install t87s[redis]       # + Redis support
pip install t87s[all]         # Everything
```

## Quick Start

```python
from t87s import T87s, MemoryAdapter, define_tags, QueryConfig

tags = define_tags({
    "user": lambda id: ("user", id),
})

t87s = T87s(adapter=MemoryAdapter())

@t87s.query
def get_user(id: str) -> QueryConfig[User]:
    return QueryConfig(
        tags=[tags["user"](id)],
        ttl="5m",
        fn=lambda: db.get_user(id),
    )
```

Full documentation: https://docs.t87s.dev
