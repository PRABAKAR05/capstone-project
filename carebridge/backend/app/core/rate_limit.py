"""In-Process Sliding-Window Rate Limiter.

Provides burst protection and abuse mitigation for sensitive API endpoints.

ARCHITECTURAL LIMITATION & SCOPE BOUNDARY:
This in-memory implementation operates on a process-local thread-safe sliding window.
In a multi-process deployment (e.g. multiple Gunicorn/Uvicorn workers) or across
multiple clustered container instances behind a load balancer, local window states
are not synchronized across processes. For multi-node production clusters, this
module should be swapped with a distributed Redis-backed rate limiter.
"""

import time
import threading
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._clients: Dict[str, List[float]] = {}

    def is_allowed(self, client_key: str) -> bool:
        """Determines if a request from client_key is permitted under the sliding window."""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Retrieve or initialize client timestamps
            timestamps = self._clients.get(client_key, [])
            # Prune timestamps older than window_start
            valid_timestamps = [ts for ts in timestamps if ts > window_start]

            if len(valid_timestamps) >= self.max_requests:
                self._clients[client_key] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._clients[client_key] = valid_timestamps
            return True

    def reset(self):
        """Resets all tracked rate-limit windows (primarily for testing)."""
        with self._lock:
            self._clients.clear()


# Default endpoint limiters
auth_rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
heavy_inference_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60)


def check_rate_limit(
    request: Request,
    limiter: Optional[SlidingWindowRateLimiter] = None,
    client_key: Optional[str] = None,
):
    """FastAPI helper to enforce rate limit on an incoming request."""
    if limiter is None:
        limiter = heavy_inference_limiter

    if not client_key:
        client_key = request.client.host if request.client else "unknown_client"

    if not limiter.is_allowed(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again.",
            headers={"Retry-After": str(limiter.window_seconds)},
        )
