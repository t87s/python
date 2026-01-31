"""t87s - Declarative cache invalidation for Python."""

from contextlib import suppress

# Adapters (async only)
from t87s.adapters import (
    AsyncMemoryAdapter,
    AsyncStorageAdapter,
)

# Duration parsing
from t87s.duration import parse_duration

# Primitives API
from t87s.primitives import Primitives, create_primitives

# QueryCache API
from t87s.query_cache import QueryCache, cached
from t87s.schema import Static, TagSchema, Wild
from t87s.typed_tag import TypedTag

# Core types
from t87s.types import (
    CacheEntry,
    Duration,
    Tag,
)

# Optional adapter imports - only available when dependencies are installed
with suppress(ImportError):
    from t87s.adapters import AsyncRedisAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncUpstashAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncCloudAdapter

__version__ = "0.1.0"

__all__ = [
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncUpstashAdapter",
    "CacheEntry",
    "Duration",
    "Primitives",
    "QueryCache",
    "Static",
    "Tag",
    "TagSchema",
    "TypedTag",
    "Wild",
    "cached",
    "create_primitives",
    "parse_duration",
]
