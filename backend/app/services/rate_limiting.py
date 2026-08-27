"""Small, process-local request limiting helpers for public cost-bearing endpoints."""

from collections import OrderedDict, deque
from collections.abc import Callable
from ipaddress import ip_address, ip_network
from threading import Lock
from time import monotonic

from fastapi import Request


GEOCODING_RATE_LIMIT = 20
GEOCODING_RATE_LIMIT_WINDOW_SECONDS = 60

_MAX_TRACKED_CLIENTS = 10_000
_TRUSTED_PROXY_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("::1/128"),
    # Host Nginx reaches the container through Docker's private bridge network.
    ip_network("172.16.0.0/12"),
)


def get_client_ip(request: Request) -> str:
    """Return a safe rate-limit identity for a request.

    The forwarding header is only used when the direct peer is a loopback or
    Docker bridge reverse proxy. The proxy must replace incoming
    X-Forwarded-For values with one validated client address before forwarding
    to the application.
    """

    direct_client = request.client.host if request.client else "unknown"

    try:
        direct_address = ip_address(direct_client)
    except ValueError:
        return direct_client

    if not any(direct_address in network for network in _TRUSTED_PROXY_NETWORKS):
        return str(direct_address)

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for or "," in forwarded_for:
        return str(direct_address)

    try:
        return str(ip_address(forwarded_for.strip()))
    except ValueError:
        return str(direct_address)


class InMemoryRateLimiter:
    """A bounded sliding-window limiter suitable for one application process."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = monotonic,
        max_clients: int = _MAX_TRACKED_CLIENTS,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._max_clients = max_clients
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def allow(self, client_ip: str) -> bool:
        now = self._clock()
        cutoff = now - self._window_seconds

        with self._lock:
            timestamps = self._requests.get(client_ip)
            if timestamps is None:
                if len(self._requests) >= self._max_clients:
                    self._requests.popitem(last=False)
                timestamps = deque()
                self._requests[client_ip] = timestamps
            else:
                self._requests.move_to_end(client_ip)

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self._limit:
                return False

            timestamps.append(now)
            return True

    def clear(self) -> None:
        """Clear state, primarily for deterministic tests."""

        with self._lock:
            self._requests.clear()


geocoding_rate_limiter = InMemoryRateLimiter(
    limit=GEOCODING_RATE_LIMIT,
    window_seconds=GEOCODING_RATE_LIMIT_WINDOW_SECONDS,
)
