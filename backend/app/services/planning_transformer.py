from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any

from geoalchemy2.elements import WKTElement


UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class PlanningApplicationTransformationError(ValueError):
    """Raised when source planning data cannot be transformed safely."""


def _clean_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlanningApplicationTransformationError(
            f"{field_name} must be a string or null."
        )

    cleaned = value.strip()
    return cleaned or None


def _clean_required_string(value: Any, field_name: str) -> str:
    cleaned = _clean_optional_string(value, field_name)
    if cleaned is None:
        raise PlanningApplicationTransformationError(
            f"{field_name} must contain a non-empty string."
        )
    return cleaned


def _clean_description(value: Any) -> str | None:
    cleaned = _clean_optional_string(value, "DevelopmentDescription")
    if cleaned is None:
        return None
    return cleaned.replace("\r\n", "\n").replace("\r", "\n")


def _epoch_milliseconds_to_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanningApplicationTransformationError(
            f"{field_name} must contain Unix epoch milliseconds or null."
        )

    try:
        epoch_milliseconds = float(value)
    except (OverflowError, ValueError) as exc:
        raise PlanningApplicationTransformationError(
            f"{field_name} contains invalid Unix epoch milliseconds."
        ) from exc
    if not isfinite(epoch_milliseconds):
        raise PlanningApplicationTransformationError(
            f"{field_name} must contain finite Unix epoch milliseconds."
        )

    try:
        return UNIX_EPOCH + timedelta(milliseconds=epoch_milliseconds)
    except (OverflowError, ValueError) as exc:
        raise PlanningApplicationTransformationError(
            f"{field_name} contains invalid Unix epoch milliseconds."
        ) from exc


def _epoch_milliseconds_to_date(value: Any, field_name: str) -> date | None:
    converted = _epoch_milliseconds_to_datetime(value, field_name)
    return converted.date() if converted is not None else None


def _transform_geometry(geometry: Any) -> WKTElement | None:
    if geometry is None:
        return None
    if not isinstance(geometry, dict):
        raise PlanningApplicationTransformationError(
            "Geometry must be a GeoJSON Point object or null."
        )
    if geometry.get("type") != "Point":
        raise PlanningApplicationTransformationError(
            "Geometry type must be 'Point'."
        )

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
        raise PlanningApplicationTransformationError(
            "Point geometry must contain exactly two coordinates."
        )

    longitude, latitude = coordinates
    if (
        isinstance(longitude, bool)
        or isinstance(latitude, bool)
        or not isinstance(longitude, (int, float))
        or not isinstance(latitude, (int, float))
    ):
        raise PlanningApplicationTransformationError(
            "Point coordinates must be finite numbers."
        )

    try:
        longitude_value = float(longitude)
        latitude_value = float(latitude)
    except (OverflowError, ValueError) as exc:
        raise PlanningApplicationTransformationError(
            "Point coordinates must be finite numbers."
        ) from exc
    if not isfinite(longitude_value) or not isfinite(latitude_value):
        raise PlanningApplicationTransformationError(
            "Point coordinates must be finite numbers."
        )
    if not -180 <= longitude_value <= 180 or not -90 <= latitude_value <= 90:
        raise PlanningApplicationTransformationError(
            "Point coordinates must be valid WGS 84 longitude and latitude values."
        )

    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def transform_planning_application(feature: dict) -> dict:
    if not isinstance(feature, dict):
        raise PlanningApplicationTransformationError("Feature must be a dictionary.")

    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise PlanningApplicationTransformationError(
            "Feature properties must be a dictionary."
        )

    source_object_id = properties.get("OBJECTID")
    if isinstance(source_object_id, bool) or not isinstance(source_object_id, int):
        raise PlanningApplicationTransformationError(
            "OBJECTID must be present and contain a valid integer."
        )

    return {
        "source_object_id": source_object_id,
        "planning_authority": _clean_required_string(
            properties.get("PlanningAuthority"),
            "PlanningAuthority",
        ),
        "application_number": _clean_required_string(
            properties.get("ApplicationNumber"),
            "ApplicationNumber",
        ),
        "description": _clean_description(
            properties.get("DevelopmentDescription")
        ),
        "address": _clean_optional_string(
            properties.get("DevelopmentAddress"),
            "DevelopmentAddress",
        ),
        "postcode": _clean_optional_string(
            properties.get("DevelopmentPostcode"),
            "DevelopmentPostcode",
        ),
        "application_status": _clean_optional_string(
            properties.get("ApplicationStatus"),
            "ApplicationStatus",
        ),
        "application_type": _clean_optional_string(
            properties.get("ApplicationType"),
            "ApplicationType",
        ),
        "decision": _clean_optional_string(
            properties.get("Decision"),
            "Decision",
        ),
        "received_date": _epoch_milliseconds_to_date(
            properties.get("ReceivedDate"),
            "ReceivedDate",
        ),
        "decision_date": _epoch_milliseconds_to_date(
            properties.get("DecisionDate"),
            "DecisionDate",
        ),
        "grant_date": _epoch_milliseconds_to_date(
            properties.get("GrantDate"),
            "GrantDate",
        ),
        "number_residential_units": properties.get("NumResidentialUnits"),
        "floor_area": properties.get("FloorArea"),
        "application_url": _clean_optional_string(
            properties.get("LinkAppDetails"),
            "LinkAppDetails",
        ),
        "location": _transform_geometry(feature.get("geometry")),
        "source_updated_at": _epoch_milliseconds_to_datetime(
            properties.get("ETL_DATE"),
            "ETL_DATE",
        ),
    }
