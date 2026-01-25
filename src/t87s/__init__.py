"""t87s - Declarative cache invalidation for Python."""

from contextlib import suppress

from t87s.adapters import (
    AsyncMemoryAdapter,
    AsyncStorageAdapter,
    MemoryAdapter,
    StorageAdapter,
    VerifiableAdapter,
)
from t87s.async_client import AsyncT87s
from t87s.client import T87s
from t87s.duration import parse_duration
from t87s.tags import define_tags, deserialize_tag, is_tag_prefix, serialize_tag
from t87s.types import (
    AsyncQueryConfig,
    CacheEntry,
    Duration,
    MutationResult,
    QueryConfig,
    Tag,
)

# Optional adapter imports - only available when dependencies are installed
with suppress(ImportError):
    from t87s.adapters import AsyncRedisAdapter, RedisAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncUpstashAdapter, UpstashAdapter

with suppress(ImportError):
    from t87s.adapters import AsyncCloudAdapter, CloudAdapter

__version__ = "0.1.0"

__all__ = [
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncQueryConfig",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncT87s",
    "AsyncUpstashAdapter",
    "CacheEntry",
    "CloudAdapter",
    "Duration",
    "MemoryAdapter",
    "MutationResult",
    "QueryConfig",
    "RedisAdapter",
    "StorageAdapter",
    "T87s",
    "Tag",
    "UpstashAdapter",
    "VerifiableAdapter",
    "define_tags",
    "deserialize_tag",
    "is_tag_prefix",
    "parse_duration",
    "serialize_tag",
]
