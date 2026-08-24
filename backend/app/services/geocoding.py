from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


GOOGLE_GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_MAPS_API_KEY_ENVIRONMENT_VARIABLE = "GOOGLE_MAPS_API_KEY"
GOOGLE_GEOCODING_TIMEOUT_SECONDS = 5.0
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE_PATH = _REPOSITORY_ROOT / ".env"

load_dotenv(_ENV_FILE_PATH)


@dataclass(frozen=True)
class GeocodedLocation:
    display_name: str
    latitude: float
    longitude: float


class GeocodingConfigurationError(RuntimeError):
    """Raised when server-side geocoding configuration is unavailable."""


class GeocodingUpstreamError(RuntimeError):
    """Raised when Google cannot provide a valid geocoding response."""


class GeocodingTimeoutError(GeocodingUpstreamError):
    """Raised when Google does not respond before the configured timeout."""


def _google_maps_api_key() -> str:
    api_key = os.getenv(GOOGLE_MAPS_API_KEY_ENVIRONMENT_VARIABLE, "").strip()
    if not api_key:
        raise GeocodingConfigurationError(
            "Google geocoding is not configured."
        )
    return api_key


def _location_from_result(result: Any) -> GeocodedLocation:
    if not isinstance(result, dict):
        raise GeocodingUpstreamError(
            "Google geocoding returned an invalid result."
        )

    display_name = result.get("formatted_address")
    geometry = result.get("geometry")
    location = geometry.get("location") if isinstance(geometry, dict) else None
    latitude = location.get("lat") if isinstance(location, dict) else None
    longitude = location.get("lng") if isinstance(location, dict) else None

    if (
        not isinstance(display_name, str)
        or not display_name.strip()
        or isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
    ):
        raise GeocodingUpstreamError(
            "Google geocoding returned an invalid result."
        )

    latitude = float(latitude)
    longitude = float(longitude)
    if (
        not math.isfinite(latitude)
        or not -90 <= latitude <= 90
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
    ):
        raise GeocodingUpstreamError(
            "Google geocoding returned invalid coordinates."
        )

    return GeocodedLocation(
        display_name=display_name.strip(),
        latitude=latitude,
        longitude=longitude,
    )


def geocode_location(query: str) -> GeocodedLocation | None:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")

    params = {
        "address": normalized_query,
        "components": "country:IE",
        "region": "ie",
        "language": "en",
        "key": _google_maps_api_key(),
    }

    try:
        response = httpx.get(
            GOOGLE_GEOCODING_URL,
            params=params,
            timeout=GOOGLE_GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise GeocodingTimeoutError(
            "Google geocoding request timed out."
        ) from exc
    except httpx.RequestError as exc:
        raise GeocodingUpstreamError(
            "Google geocoding request failed."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise GeocodingUpstreamError(
            "Google geocoding request failed."
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise GeocodingUpstreamError(
            "Google geocoding returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise GeocodingUpstreamError(
            "Google geocoding returned an invalid response."
        )

    status = payload.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        raise GeocodingUpstreamError(
            "Google geocoding returned an unsuccessful response."
        )

    results = payload.get("results")
    if not isinstance(results, list):
        raise GeocodingUpstreamError(
            "Google geocoding returned an invalid response."
        )
    if not results:
        return None

    return _location_from_result(results[0])
