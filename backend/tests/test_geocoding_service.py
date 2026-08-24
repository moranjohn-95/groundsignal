from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from backend.app.services import geocoding
from backend.app.services.geocoding import (
    GOOGLE_GEOCODING_TIMEOUT_SECONDS,
    GOOGLE_GEOCODING_URL,
    GeocodingConfigurationError,
    GeocodingTimeoutError,
    GeocodingUpstreamError,
    geocode_location,
)


def test_geocoding_loads_environment_from_repository_root() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    assert geocoding._ENV_FILE_PATH == repository_root / ".env"


def _google_response(payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", GOOGLE_GEOCODING_URL)
    return httpx.Response(status_code, json=payload, request=request)


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_maps_first_irish_result(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "server-only-key")
    mock_get.return_value = _google_response(
        {
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Tralee, Co. Kerry, Ireland",
                    "geometry": {
                        "location": {
                            "lat": 52.2704,
                            "lng": -9.7026,
                        }
                    },
                }
            ],
        }
    )

    result = geocode_location("  Tralee  ")

    assert result is not None
    assert result.display_name == "Tralee, Co. Kerry, Ireland"
    assert result.latitude == 52.2704
    assert result.longitude == -9.7026
    mock_get.assert_called_once_with(
        GOOGLE_GEOCODING_URL,
        params={
            "address": "Tralee",
            "components": "country:IE",
            "region": "ie",
            "language": "en",
            "key": "server-only-key",
        },
        timeout=GOOGLE_GEOCODING_TIMEOUT_SECONDS,
    )


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_returns_none_for_zero_results(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    mock_get.return_value = _google_response(
        {"status": "ZERO_RESULTS", "results": []}
    )

    assert geocode_location("Not a real Irish location") is None


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_rejects_empty_query_before_request(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")

    with pytest.raises(ValueError, match="query must not be empty"):
        geocode_location("   ")

    mock_get.assert_not_called()


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_requires_server_api_key(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    with pytest.raises(GeocodingConfigurationError):
        geocode_location("Killarney, Co. Kerry")

    mock_get.assert_not_called()


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_handles_google_api_failure_without_key_leak(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "secret-google-key"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", api_key)
    mock_get.return_value = _google_response(
        {
            "status": "REQUEST_DENIED",
            "error_message": f"The provided API key {api_key} is invalid.",
            "results": [],
        }
    )

    with pytest.raises(GeocodingUpstreamError) as exc_info:
        geocode_location("Tralee")

    assert api_key not in str(exc_info.value)


@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_handles_upstream_http_failure(
    mock_get,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    mock_get.return_value = _google_response({}, status_code=503)

    with pytest.raises(GeocodingUpstreamError):
        geocode_location("Tralee")


@pytest.mark.parametrize(
    ("request_error", "expected_exception"),
    [
        (httpx.ReadTimeout("Timed out"), GeocodingTimeoutError),
        (httpx.ConnectError("Connection failed"), GeocodingUpstreamError),
    ],
)
@patch("backend.app.services.geocoding.httpx.get")
def test_geocode_location_handles_timeout_and_network_failures(
    mock_get,
    request_error: httpx.RequestError,
    expected_exception: type[Exception],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    mock_get.side_effect = request_error

    with pytest.raises(expected_exception):
        geocode_location("Tralee")
