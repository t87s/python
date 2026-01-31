"""Storage adapters for t87s cache library (async only)."""

from contextlib import suppress

from t87s.adapters.base import (
    AsyncStorageAdapter,
    AsyncVerifiableAdapter,
)
from t87s.adapters.memory import AsyncMemoryAdapter

# Optional adapters - only available when dependencies are installed
with suppress(ImportError):
    from t87s.adapters.redis import AsyncRedisAdapter

with suppress(ImportError):
    from t87s.adapters.upstash import AsyncUpstashAdapter

with suppress(ImportError):
    from t87s.adapters.cloud import AsyncCloudAdapter

__all__ = [
    "AsyncCloudAdapter",
    "AsyncMemoryAdapter",
    "AsyncRedisAdapter",
    "AsyncStorageAdapter",
    "AsyncUpstashAdapter",
    "AsyncVerifiableAdapter",
]
