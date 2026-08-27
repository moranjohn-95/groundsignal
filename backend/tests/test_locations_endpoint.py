import pytest
from fastapi.testclient import TestClient

from backend.app.api import locations
from backend.app.main import app
from backend.app.services.geocoding import (
    GeocodedLocation,
    GeocodingConfigurationError,
    GeocodingTimeoutError,
    GeocodingUpstreamError,
)
from backend.app.services.rate_limiting import (
    GEOCODING_RATE_LIMIT,
    geocoding_rate_limiter,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_geocoding_rate_limit() -> None:
    geocoding_rate_limiter.clear()
    yield
    geocoding_rate_limiter.clear()


def test_geocode_endpoint_returns_normalized_query_and_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_queries: list[str] = []

    def fake_geocode(query: str) -> GeocodedLocation:
        captured_queries.append(query)
        return GeocodedLocation(
            display_name="Killarney, Co. Kerry, Ireland",
            latitude=52.0599,
            longitude=-9.5044,
        )

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)

    response = client.get(
        "/api/v1/locations/geocode",
        params={"query": "  Killarney, Co. Kerry  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "Killarney, Co. Kerry",
        "display_name": "Killarney, Co. Kerry, Ireland",
        "latitude": 52.0599,
        "longitude": -9.5044,
    }
    assert captured_queries == ["Killarney, Co. Kerry"]


def test_geocode_endpoint_returns_404_when_location_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locations, "geocode_location", lambda _query: None)

    response = client.get(
        "/api/v1/locations/geocode",
        params={"query": "Not a real Irish location"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Location not found."}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"query": ""},
        {"query": "   "},
    ],
)
def test_geocode_endpoint_rejects_invalid_query(params: dict[str, str]) -> None:
    response = client.get("/api/v1/locations/geocode", params=params)

    assert response.status_code == 422


def test_geocode_endpoint_accepts_query_at_maximum_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = "x" * 200
    monkeypatch.setattr(
        locations,
        "geocode_location",
        lambda _query: GeocodedLocation(
            display_name="Example, Ireland",
            latitude=52.0,
            longitude=-9.0,
        ),
    )

    response = client.get("/api/v1/locations/geocode", params={"query": query})

    assert response.status_code == 200
    assert response.json()["query"] == query


def test_geocode_endpoint_rejects_overlong_query_without_calling_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_geocode(_query: str) -> GeocodedLocation:
        nonlocal called
        called = True
        raise AssertionError("Geocoding service must not be called")

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)

    response = client.get(
        "/api/v1/locations/geocode",
        params={"query": "x" * 201},
    )

    assert response.status_code == 422
    assert called is False


def test_geocode_endpoint_allows_requests_within_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_geocode(_query: str) -> GeocodedLocation:
        nonlocal calls
        calls += 1
        return GeocodedLocation(
            display_name="Example, Ireland",
            latitude=52.0,
            longitude=-9.0,
        )

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)

    for _ in range(GEOCODING_RATE_LIMIT):
        response = client.get("/api/v1/locations/geocode", params={"query": "Tralee"})
        assert response.status_code == 200

    assert calls == GEOCODING_RATE_LIMIT


def test_geocode_endpoint_rate_limit_prevents_google_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_geocode(_query: str) -> GeocodedLocation:
        nonlocal calls
        calls += 1
        return GeocodedLocation(
            display_name="Example, Ireland",
            latitude=52.0,
            longitude=-9.0,
        )

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)

    for _ in range(GEOCODING_RATE_LIMIT):
        assert client.get(
            "/api/v1/locations/geocode", params={"query": "Tralee"}
        ).status_code == 200

    response = client.get("/api/v1/locations/geocode", params={"query": "Tralee"})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert calls == GEOCODING_RATE_LIMIT


def test_geocode_endpoint_limits_clients_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_geocode(_query: str) -> GeocodedLocation:
        nonlocal calls
        calls += 1
        return GeocodedLocation(
            display_name="Example, Ireland",
            latitude=52.0,
            longitude=-9.0,
        )

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)
    first_client = TestClient(app, client=("198.51.100.10", 50000))
    second_client = TestClient(app, client=("198.51.100.11", 50000))

    for _ in range(GEOCODING_RATE_LIMIT):
        assert first_client.get(
            "/api/v1/locations/geocode", params={"query": "Tralee"}
        ).status_code == 200

    assert first_client.get(
        "/api/v1/locations/geocode", params={"query": "Tralee"}
    ).status_code == 429
    assert second_client.get(
        "/api/v1/locations/geocode", params={"query": "Tralee"}
    ).status_code == 200
    assert calls == GEOCODING_RATE_LIMIT + 1


def test_geocode_endpoint_does_not_trust_forwarding_headers_from_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_geocode(_query: str) -> GeocodedLocation:
        nonlocal calls
        calls += 1
        return GeocodedLocation(
            display_name="Example, Ireland",
            latitude=52.0,
            longitude=-9.0,
        )

    monkeypatch.setattr(locations, "geocode_location", fake_geocode)
    untrusted_client = TestClient(app, client=("198.51.100.10", 50000))

    for request_number in range(GEOCODING_RATE_LIMIT):
        response = untrusted_client.get(
            "/api/v1/locations/geocode",
            params={"query": "Tralee"},
            headers={"X-Forwarded-For": f"203.0.113.{request_number}"},
        )
        assert response.status_code == 200

    response = untrusted_client.get(
        "/api/v1/locations/geocode",
        params={"query": "Tralee"},
        headers={"X-Forwarded-For": "203.0.113.200"},
    )

    assert response.status_code == 429
    assert calls == GEOCODING_RATE_LIMIT


def test_geocode_endpoint_handles_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_configuration(_query: str):
        raise GeocodingConfigurationError("Internal configuration detail")

    monkeypatch.setattr(locations, "geocode_location", missing_configuration)

    response = client.get(
        "/api/v1/locations/geocode",
        params={"query": "Tralee"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Geocoding service is unavailable."}


@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_detail"),
    [
        (
            GeocodingUpstreamError("secret-google-key upstream detail"),
            502,
            "Geocoding service request failed.",
        ),
        (
            GeocodingTimeoutError("secret-google-key timeout detail"),
            504,
            "Geocoding service timed out.",
        ),
    ],
)
def test_geocode_endpoint_hides_upstream_errors_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    def fail_geocoding(_query: str):
        raise exception

    monkeypatch.setattr(locations, "geocode_location", fail_geocoding)

    response = client.get(
        "/api/v1/locations/geocode",
        params={"query": "Tralee"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "secret-google-key" not in response.text
