from backend.app.services.rate_limiting import InMemoryRateLimiter


def test_rate_limiter_evicts_oldest_client_when_capacity_is_reached() -> None:
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60, max_clients=2)

    assert limiter.allow("first")
    assert limiter.allow("second")
    assert limiter.allow("third")

    assert len(limiter._requests) == 2
    assert "first" not in limiter._requests
