from unittest.mock import Mock, patch

import httpx
import pytest

from backend.app.services.planning_api import (
    PLANNING_APPLICATIONS_LAYER_URL,
    PlanningAPIResponseError,
    fetch_planning_applications,
    iter_planning_application_pages,
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


def _response_with_features(features: list[object]) -> Mock:
    response = Mock()
    response.json.return_value = {
        "type": "FeatureCollection",
        "features": features,
    }
    return response


@patch("backend.app.services.planning_api.httpx.get")
def test_pages_use_deterministic_order_and_actual_returned_offset(
    mock_get: Mock,
) -> None:
    first_page = [{"id": 1}, {"id": 2}]
    second_page = [{"id": 3}]
    mock_get.side_effect = [
        _response_with_features(first_page),
        _response_with_features(second_page),
    ]

    pages = list(iter_planning_application_pages(page_size=2))

    assert pages == [first_page, second_page]
    assert mock_get.call_count == 2
    first_params = mock_get.call_args_list[0].kwargs["params"]
    second_params = mock_get.call_args_list[1].kwargs["params"]
    assert first_params["resultOffset"] == 0
    assert second_params["resultOffset"] == 2
    assert first_params["resultRecordCount"] == 2
    assert second_params["resultRecordCount"] == 2
    assert first_params["orderByFields"] == "OBJECTID ASC"
    assert second_params["orderByFields"] == "OBJECTID ASC"
    assert first_params["returnGeometry"] == "true"
    assert first_params["outSR"] == 4326
    assert first_params["f"] == "geojson"


@patch("backend.app.services.planning_api.httpx.get")
def test_pagination_stops_after_short_page(mock_get: Mock) -> None:
    short_page = [{"id": 1}]
    mock_get.return_value = _response_with_features(short_page)

    pages = list(iter_planning_application_pages(page_size=2))

    assert pages == [short_page]
    mock_get.assert_called_once()


@patch("backend.app.services.planning_api.httpx.get")
def test_pagination_stops_after_empty_page(mock_get: Mock) -> None:
    full_page = [{"id": 1}, {"id": 2}]
    mock_get.side_effect = [
        _response_with_features(full_page),
        _response_with_features([]),
    ]

    pages = list(iter_planning_application_pages(page_size=2))

    assert pages == [full_page]
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[1].kwargs["params"]["resultOffset"] == 2


@pytest.mark.parametrize("page_size", [0, -1, 2001, True, 1.5])
def test_invalid_page_size_is_rejected(page_size: object) -> None:
    with patch("backend.app.services.planning_api.httpx.get") as mock_get:
        with pytest.raises(ValueError, match="between 1 and 2000"):
            list(iter_planning_application_pages(page_size=page_size))

    mock_get.assert_not_called()


@pytest.mark.parametrize("page_size", [1, 2000])
@patch("backend.app.services.planning_api.httpx.get")
def test_page_size_boundaries_are_allowed(mock_get: Mock, page_size: int) -> None:
    mock_get.return_value = _response_with_features([])

    assert list(iter_planning_application_pages(page_size=page_size)) == []
    assert mock_get.call_args.kwargs["params"]["resultRecordCount"] == page_size


@patch("backend.app.services.planning_api.httpx.get")
def test_pagination_http_failure_propagates(mock_get: Mock) -> None:
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
        next(iter_planning_application_pages())

    assert exc_info.value is http_error
    mocked_response.json.assert_not_called()


@patch("backend.app.services.planning_api.httpx.get")
def test_pagination_malformed_response_raises_application_error(
    mock_get: Mock,
) -> None:
    response = Mock()
    response.json.return_value = {"features": None}
    mock_get.return_value = response

    with pytest.raises(PlanningAPIResponseError):
        next(iter_planning_application_pages())
