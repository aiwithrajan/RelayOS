"""In-memory sliding window rate limiter for RelayOS tenants."""
import time
from collections import defaultdict
from typing import Dict, List, Tuple


class TenantRateLimiter:
    def __init__(self):
        # Maps tenant_slug -> list of request timestamps (seconds)
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, tenant_slug: str, limit_rpm: int) -> Tuple[bool, int, int]:
        """Check if request is allowed under allocated RPM limit.

        Args:
            tenant_slug: Tenant slug.
            limit_rpm: Max allowed requests per minute.

        Returns:
            Tuple[bool, int, int]: (allowed, current_count, limit_rpm)
        """
        now = time.time()
        window_start = now - 60.0

        # Filter out timestamps older than 60s
        valid_timestamps = [t for t in self._requests[tenant_slug] if t > window_start]
        self._requests[tenant_slug] = valid_timestamps

        if len(valid_timestamps) >= limit_rpm:
            return False, len(valid_timestamps), limit_rpm

        self._requests[tenant_slug].append(now)
        return True, len(self._requests[tenant_slug]), limit_rpm

    def reset(self, tenant_slug: str = None):
        """Reset rate limiter state for tests."""
        if tenant_slug:
            self._requests[tenant_slug] = []
        else:
            self._requests.clear()


# Global rate limiter instance
tenant_rate_limiter = TenantRateLimiter()
