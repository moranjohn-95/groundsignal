from unittest.mock import Mock, patch

import httpx
import pytest

from backend.app.services.planning_api import (
    PLANNING_APPLICATIONS_LAYER_URL,
    PlanningAPIResponseError,
    fetch_planning_applications,
)


@patch("backend.app.services.planning_api.httpx.get")
def test_successful_response_returns_raw_features(mock_get: Mock) -> None:
    features = [
        {
            "type": "Feature",
            "properties": {"OBJECTID": 1},
            "geometry": {"type": "Point", "coordinates": [-6.26, 53.35]},
        }
    ]
    response = Mock()
    response.json.return_value = {
        "type": "FeatureCollection",
        "features": features,
    }
    mock_get.return_value = response

    result = fetch_planning_applications(limit=1)

    assert result is features
    mock_get.assert_called_once_with(
        f"{PLANNING_APPLICATIONS_LAYER_URL}/query",
        params={
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "f": "geojson",
            "resultRecordCount": 1,
        },
        timeout=10.0,
    )
    response.raise_for_status.assert_called_once_with()


@pytest.mark.parametrize("limit", [0, -1, 101, True])
def test_invalid_limit_is_rejected(limit: int) -> None:
    with patch("backend.app.services.planning_api.httpx.get") as mock_get:
        with pytest.raises(ValueError, match="between 1 and 100"):
            fetch_planning_applications(limit=limit)

    mock_get.assert_not_called()


@patch("backend.app.services.planning_api.httpx.get")
def test_http_failure_propagates(mock_get: Mock) -> None:
    request = httpx.Request("GET", f"{PLANNING_APPLICATIONS_LAYER_URL}/query")
    response = httpx.Response(503, request=request)
    http_error = httpx.HTTPStatusError(
        "Service unavailable",
        request=request,
        response=response,
    )
    mocked_response = Mock()
    mocked_response.raise_for_status.side_effect = http_error
    mock_get.return_value = mocked_response

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        fetch_planning_applications()

    assert exc_info.value is http_error
    mocked_response.json.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"features": None},
        {"features": {}},
    ],
)
@patch("backend.app.services.planning_api.httpx.get")
def test_malformed_response_raises_application_error(
    mock_get: Mock,
    payload: object,
) -> None:
    response = Mock()
    response.json.return_value = payload
    mock_get.return_value = response

    with pytest.raises(PlanningAPIResponseError):
        fetch_planning_applications()
