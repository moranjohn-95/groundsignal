import pytest

from backend.app.services.rate_limiting import (
    database_request_rate_limiter,
    geocoding_rate_limiter,
)


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> None:
    """Keep process-local rate limiter state isolated between tests."""

    geocoding_rate_limiter.clear()
    database_request_rate_limiter.clear()
    yield
    geocoding_rate_limiter.clear()
    database_request_rate_limiter.clear()
