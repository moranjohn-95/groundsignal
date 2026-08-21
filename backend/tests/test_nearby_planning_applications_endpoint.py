from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db
from backend.app.main import app
from backend.app.models import PlanningApplication


def _application(*, identifier: int, source_object_id: int) -> PlanningApplication:
    return PlanningApplication(
        id=identifier,
        source_object_id=source_object_id,
        planning_authority="Test Council",
        application_number=f"APP-{source_object_id}",
        description="Test development",
        address="1 Test Street",
        postcode="D01 TEST",
        application_status="Decided",
        application_type="Permission",
        decision="Granted",
        received_date=date(2025, 1, 2),
        decision_date=date(2025, 2, 3),
        grant_date=date(2025, 3, 4),
        number_residential_units=2,
        floor_area=150.5,
        application_url="https://example.test/application",
        source_updated_at=datetime(2025, 4, 5, tzinfo=timezone.utc),
    )


@pytest.fixture
def nearby_client():
    session = Mock(spec=Session)
    session.scalar.return_value = 0
    session.execute.return_value.all.return_value = []

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.clear()


def _valid_params(**overrides):
    params = {
        "latitude": 53.3498,
        "longitude": -6.2603,
        "radius_km": 5,
    }
    params.update(overrides)
    return params


@pytest.mark.parametrize("latitude", [-90.01, 90.01])
def test_nearby_rejects_invalid_latitude(nearby_client, latitude):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(latitude=latitude),
    )

    assert response.status_code == 422
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.parametrize("longitude", [-180.01, 180.01])
def test_nearby_rejects_invalid_longitude(nearby_client, longitude):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(longitude=longitude),
    )

    assert response.status_code == 422
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.parametrize("radius_km", [0, -1, 50.01])
def test_nearby_rejects_invalid_radius(nearby_client, radius_km):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(radius_km=radius_km),
    )

    assert response.status_code == 422
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.parametrize(
    "pagination",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_nearby_rejects_invalid_pagination(nearby_client, pagination):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(**pagination),
    )

    assert response.status_code == 422
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


def test_nearby_returns_paginated_items_with_distance(nearby_client):
    client, session = nearby_client
    session.scalar.return_value = 37
    session.execute.return_value.all.return_value = [
        (_application(identifier=1, source_object_id=101), 1.25),
        (_application(identifier=2, source_object_id=102), 2.5),
    ]

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(limit=5, offset=10),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 5
    assert payload["offset"] == 10
    assert payload["total"] == 37
    assert [item["distance_km"] for item in payload["items"]] == [1.25, 2.5]
    assert payload["items"][0]["source_object_id"] == 101
    assert "location" not in payload["items"][0]
    assert "created_at" not in payload["items"][0]
    assert "updated_at" not in payload["items"][0]


def test_nearby_uses_default_pagination(nearby_client):
    client, _ = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 20,
        "offset": 0,
        "total": 0,
    }


def test_nearby_builds_postgis_geography_queries(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(radius_km=7.5, limit=12, offset=4),
    )

    assert response.status_code == 200
    count_statement = session.scalar.call_args.args[0]
    item_statement = session.execute.call_args.args[0]
    dialect = postgresql.dialect()
    count_compiled = count_statement.compile(dialect=dialect)
    item_compiled = item_statement.compile(dialect=dialect)
    count_sql = str(count_compiled)
    item_sql = str(item_compiled)

    assert "ST_DWithin" in count_sql
    assert "ST_DWithin" in item_sql
    assert "ST_Distance" in item_sql
    assert "ST_SetSRID" in item_sql
    assert "ST_MakePoint" in item_sql
    assert "CAST" in item_sql
    assert "geography(POINT,4326)" in item_sql
    assert "ORDER BY distance_km ASC, planning_applications.id ASC" in item_sql

    count_values = set(count_compiled.params.values())
    item_values = set(item_compiled.params.values())
    assert {-6.2603, 53.3498, 4326, 7500.0}.issubset(count_values)
    assert {-6.2603, 53.3498, 4326, 7500.0, 1000.0, 12, 4}.issubset(
        item_values
    )
