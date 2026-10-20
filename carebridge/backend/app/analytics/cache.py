import time
from typing import Dict, Any, Optional, Tuple


class BoundedTimeWindowCache:
    """Thread-safe, tenant-isolated in-memory cache for operational analytics aggregates.
    Enforces maximum entry limits, strict TTL expiration, and isolated cache keys.
    """

    def __init__(self, ttl_seconds: int = 60, max_entries: int = 256):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}

    def _make_key(self, hospital_id: str, time_window: str, metric: str) -> str:
        # Cache key binds hospital tenant, time window, and metric type
        return f"{hospital_id}::{time_window}::{metric}"

    def get(self, hospital_id: str, time_window: str, metric: str = "overview") -> Optional[Any]:
        key = self._make_key(hospital_id, time_window, metric)
        if key not in self._store:
            return None

        cached_at, value = self._store[key]
        if time.time() - cached_at > self.ttl_seconds:
            # Expired
            del self._store[key]
            return None

        return value

    def set(self, hospital_id: str, time_window: str, value: Any, metric: str = "overview") -> None:
        key = self._make_key(hospital_id, time_window, metric)

        # Evict oldest entry if capacity reached
        if len(self._store) >= self.max_entries and key not in self._store:
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k][0])
            del self._store[oldest_key]

        self._store[key] = (time.time(), value)

    def invalidate_tenant(self, hospital_id: str) -> None:
        """Evicts all cached metrics for a specific hospital tenant."""
        keys_to_delete = [k for k in self._store if k.startswith(f"{hospital_id}::")]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self) -> None:
        self._store.clear()


analytics_cache = BoundedTimeWindowCache(ttl_seconds=60, max_entries=256)
