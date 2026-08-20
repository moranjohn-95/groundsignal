from typing import Any

import httpx


PLANNING_APPLICATIONS_LAYER_URL = (
    "https://services.arcgis.com/NzlPQPKn5QF9v2US/ArcGIS/rest/services/"
    "IrishPlanningApplications/FeatureServer/0"
)


class PlanningAPIResponseError(RuntimeError):
    """Raised when the planning API returns an invalid response."""


def fetch_planning_applications(limit: int = 5) -> list[Any]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")

    response = httpx.get(
        f"{PLANNING_APPLICATIONS_LAYER_URL}/query",
        params={
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "geojson",
            "resultRecordCount": limit,
        },
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
