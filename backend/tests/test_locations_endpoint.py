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


client = TestClient(app)


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
        {"query": "x" * 201},
    ],
)
def test_geocode_endpoint_rejects_invalid_query(params: dict[str, str]) -> None:
    response = client.get("/api/v1/locations/geocode", params=params)

    assert response.status_code == 422


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
