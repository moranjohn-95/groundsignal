from collections.abc import Iterator
from typing import Any

import httpx


PLANNING_APPLICATIONS_LAYER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/ArcGIS/rest/services/"
    "IrishPlanningApplications/FeatureServer/0"
)


class PlanningAPIResponseError(RuntimeError):
    """Raised when the planning API returns an invalid response."""


def _fetch_planning_application_page(
    result_record_count: int,
    *,
    result_offset: int | None = None,
    order_by_fields: str | None = None,
) -> list[Any]:
    params: dict[str, str | int] = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
        "resultRecordCount": result_record_count,
    }
    if result_offset is not None:
        params["resultOffset"] = result_offset
    if order_by_fields is not None:
        params["orderByFields"] = order_by_fields

    response = httpx.get(
        f"{PLANNING_APPLICATIONS_LAYER_URL}/query",
        params=params,
        timeout=10.0,
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise PlanningAPIResponseError(
            "Planning API returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise PlanningAPIResponseError(
            "Planning API response must be a JSON object."
        )

    features = payload.get("features")
    if not isinstance(features, list):
        raise PlanningAPIResponseError(
            "Planning API response must contain a 'features' list."
        )

    return features


def fetch_planning_applications(limit: int = 5) -> list[Any]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")

    return _fetch_planning_application_page(result_record_count=limit)


def iter_planning_application_pages(page_size: int = 500) -> Iterator[list[Any]]:
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= 2000
    ):
        raise ValueError("page_size must be an integer between 1 and 2000")

    offset = 0
    while True:
        features = _fetch_planning_application_page(
            result_record_count=page_size,
            result_offset=offset,
            order_by_fields="OBJECTID ASC",
        )
        if not features:
            return

        yield features

        returned_count = len(features)
        if returned_count < page_size:
            return
        offset += returned_count
