from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from backend.app.services.planning_transformer import (
    PlanningApplicationTransformationError,
    transform_planning_application,
)


VALID_FEATURE = {
    "type": "Feature",
    "properties": {
        "OBJECTID": 123,
        "PlanningAuthority": "  Carlow County Council  ",
        "ApplicationNumber": "  24/123  ",
        "DevelopmentDescription": "  Construction of a dwelling.\r\n",
        "DevelopmentAddress": "  Main Street, Carlow  ",
        "DevelopmentPostcode": "  R93 ABC1  ",
        "ApplicationStatus": "  Decided  ",
        "ApplicationType": "  Permission  ",
        "Decision": "  Granted  ",
        "ReceivedDate": 1704067200000,
        "DecisionDate": 1706745600000,
        "GrantDate": 1709251200000,
        "NumResidentialUnits": 2,
        "FloorArea": 145.5,
        "LinkAppDetails": "  https://example.test/planning/24-123  ",
        "ETL_DATE": 1709251200000,
    },
    "geometry": {
        "type": "Point",
        "coordinates": [-6.93020440228109, 52.8397786273211],
    },
}


def test_complete_valid_feature_transforms_correctly() -> None:
    result = transform_planning_application(deepcopy(VALID_FEATURE))

    assert result["source_object_id"] == 123
    assert result["planning_authority"] == "Carlow County Council"
    assert result["application_number"] == "24/123"
    assert result["description"] == "Construction of a dwelling."
    assert result["address"] == "Main Street, Carlow"
    assert result["postcode"] == "R93 ABC1"
    assert result["application_status"] == "Decided"
    assert result["application_type"] == "Permission"
    assert result["decision"] == "Granted"
    assert result["number_residential_units"] == 2
    assert result["floor_area"] == 145.5
    assert result["application_url"] == "https://example.test/planning/24-123"


def test_epoch_millisecond_dates_are_converted() -> None:
    result = transform_planning_application(deepcopy(VALID_FEATURE))

    assert result["received_date"] == date(2024, 1, 1)
    assert result["decision_date"] == date(2024, 2, 1)
    assert result["grant_date"] == date(2024, 3, 1)
    assert result["source_updated_at"] == datetime(
        2024,
        3,
        1,
        tzinfo=timezone.utc,
    )


def test_description_line_endings_and_outer_whitespace_are_cleaned() -> None:
    feature = deepcopy(VALID_FEATURE)
    feature["properties"]["DevelopmentDescription"] = (
        "  First line\r\nSecond line\r\n  "
    )

    result = transform_planning_application(feature)

    assert result["description"] == "First line\nSecond line"


def test_empty_optional_strings_become_none() -> None:
    feature = deepcopy(VALID_FEATURE)
    optional_fields = [
        "DevelopmentDescription",
        "DevelopmentAddress",
        "DevelopmentPostcode",
        "ApplicationStatus",
        "ApplicationType",
        "Decision",
        "LinkAppDetails",
    ]
    for field_name in optional_fields:
        feature["properties"][field_name] = " \r\n\t "

    result = transform_planning_application(feature)

    assert result["description"] is None
    assert result["address"] is None
    assert result["postcode"] is None
    assert result["application_status"] is None
    assert result["application_type"] is None
    assert result["decision"] is None
    assert result["application_url"] is None


def test_nullable_dates_remain_none() -> None:
    feature = deepcopy(VALID_FEATURE)
    for field_name in ["ReceivedDate", "DecisionDate", "GrantDate", "ETL_DATE"]:
        feature["properties"][field_name] = None

    result = transform_planning_application(feature)

    assert result["received_date"] is None
    assert result["decision_date"] is None
    assert result["grant_date"] is None
    assert result["source_updated_at"] is None


def test_valid_point_geometry_becomes_wkt_element() -> None:
    result = transform_planning_application(deepcopy(VALID_FEATURE))

    assert result["location"].data == (
        "POINT(-6.93020440228109 52.8397786273211)"
    )
    assert result["location"].srid == 4326


@pytest.mark.parametrize("geometry", [None, pytest.param("missing", id="missing")])
def test_missing_or_null_geometry_becomes_none(geometry: object) -> None:
    feature = deepcopy(VALID_FEATURE)
    if geometry == "missing":
        feature.pop("geometry")
    else:
        feature["geometry"] = geometry

    result = transform_planning_application(feature)

    assert result["location"] is None


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "LineString", "coordinates": [[-6.9, 52.8], [-6.8, 52.9]]},
        {"type": "Point", "coordinates": [-6.9]},
        {"type": "Point", "coordinates": ["-6.9", 52.8]},
        {"type": "Point", "coordinates": [181, 52.8]},
        {"type": "Point", "coordinates": [-6.9, 91]},
    ],
)
def test_malformed_geometry_is_rejected(geometry: object) -> None:
    feature = deepcopy(VALID_FEATURE)
    feature["geometry"] = geometry

    with pytest.raises(PlanningApplicationTransformationError, match="Geometry|geometry|coordinates"):
        transform_planning_application(feature)


@pytest.mark.parametrize("object_id", [None, "123", 123.0, True])
def test_missing_or_invalid_object_id_is_rejected(object_id: object) -> None:
    feature = deepcopy(VALID_FEATURE)
    if object_id is None:
        feature["properties"].pop("OBJECTID")
    else:
        feature["properties"]["OBJECTID"] = object_id

    with pytest.raises(PlanningApplicationTransformationError, match="OBJECTID"):
        transform_planning_application(feature)


@pytest.mark.parametrize("planning_authority", [None, "", " \r\n ", 123])
def test_missing_or_blank_planning_authority_is_rejected(
    planning_authority: object,
) -> None:
    feature = deepcopy(VALID_FEATURE)
    feature["properties"]["PlanningAuthority"] = planning_authority

    with pytest.raises(
        PlanningApplicationTransformationError,
        match="PlanningAuthority",
    ):
        transform_planning_application(feature)


@pytest.mark.parametrize("application_number", [None, "", " \r\n ", 123])
def test_missing_or_blank_application_number_is_rejected(
    application_number: object,
) -> None:
    feature = deepcopy(VALID_FEATURE)
    feature["properties"]["ApplicationNumber"] = application_number

    with pytest.raises(
        PlanningApplicationTransformationError,
        match="ApplicationNumber",
    ):
        transform_planning_application(feature)


@pytest.mark.parametrize("feature", [None, [], "feature"])
def test_feature_must_be_a_dictionary(feature: object) -> None:
    with pytest.raises(PlanningApplicationTransformationError, match="Feature"):
        transform_planning_application(feature)


@pytest.mark.parametrize("properties", [None, [], "properties"])
def test_properties_must_be_a_dictionary(properties: object) -> None:
    feature = deepcopy(VALID_FEATURE)
    feature["properties"] = properties

    with pytest.raises(PlanningApplicationTransformationError, match="properties"):
        transform_planning_application(feature)
