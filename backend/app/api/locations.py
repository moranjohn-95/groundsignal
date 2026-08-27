from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..schemas import LocationGeocodeResponse
from ..services.geocoding import (
    GeocodingConfigurationError,
    GeocodingTimeoutError,
    GeocodingUpstreamError,
    geocode_location,
)
from ..services.rate_limiting import get_client_ip, geocoding_rate_limiter


router = APIRouter(
    prefix="/api/v1/locations",
    tags=["locations"],
)


@router.get("/geocode", response_model=LocationGeocodeResponse)
def geocode(
    request: Request,
    query: Annotated[str, Query(min_length=1, max_length=200)],
) -> LocationGeocodeResponse:
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Location query must not be empty.",
        )

    if not geocoding_rate_limiter.allow(get_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many geocoding requests. Please try again later.",
            headers={"Retry-After": "60"},
        )

    try:
        location = geocode_location(normalized_query)
    except GeocodingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service is unavailable.",
        ) from exc
    except GeocodingTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Geocoding service timed out.",
        ) from exc
    except GeocodingUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Geocoding service request failed.",
        ) from exc

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found.",
        )

    return LocationGeocodeResponse(
        query=normalized_query,
        display_name=location.display_name,
        latitude=location.latitude,
        longitude=location.longitude,
    )
