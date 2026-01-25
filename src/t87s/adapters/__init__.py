"""Storage adapters for t87s cache library."""

from contextlib import suppress

from t87s.adapters.base import (
    AsyncStorageAdapter,
    StorageAdapter,
    VerifiableAdapter,
)
from t87s.adapters.memory import AsyncMemoryAdapter, MemoryAdapter

# Optional adapters - only available when dependencies are installed
with suppress(ImportError):
    from t87s.adapters.redis import AsyncRedisAdapter, RedisAdapter

with suppress(ImportError):
    from t87s.adapters.upstash import AsyncUpstashAdapter, UpstashAdapter

with suppress(ImportError):
    from t87s.adapters.cloud import AsyncCloudAdapter, CloudAdapter

__all__ = [
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncUpstashAdapter",
    "CloudAdapter",
    "MemoryAdapter",
    "RedisAdapter",
    "StorageAdapter",
    "UpstashAdapter",
    "VerifiableAdapter",
]
