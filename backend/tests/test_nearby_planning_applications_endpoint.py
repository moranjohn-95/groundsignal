from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.api import planning_applications
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


def _compiled_statements(session):
    dialect = postgresql.dialect()
    count_statement = session.scalar.call_args.args[0]
    item_statement = session.execute.call_args.args[0]
    return (
        count_statement.compile(dialect=dialect),
        item_statement.compile(dialect=dialect),
    )


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
    assert [item["category"] for item in payload["items"]] == [
        "residential",
        "residential",
    ]
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


@pytest.mark.parametrize(
    ("parameter", "value", "expected_value", "sql_predicate"),
    [
        (
            "received_from",
            "2025-01-02",
            date(2025, 1, 2),
            "planning_applications.received_date >=",
        ),
        (
            "received_to",
            "2025-03-04",
            date(2025, 3, 4),
            "planning_applications.received_date <=",
        ),
        (
            "application_status",
            "Pending",
            "Pending",
            "planning_applications.application_status =",
        ),
        (
            "decision",
            "Refused",
            "Refused",
            "planning_applications.decision =",
        ),
        (
            "category",
            "commercial",
            "commercial",
            "planning_applications.category =",
        ),
    ],
)
def test_nearby_applies_individual_relevance_filters(
    nearby_client,
    parameter,
    value,
    expected_value,
    sql_predicate,
):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(**{parameter: value}),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
    assert sql_predicate in str(count_compiled)
    assert sql_predicate in str(item_compiled)
    assert expected_value in count_compiled.params.values()
    assert expected_value in item_compiled.params.values()


def test_nearby_date_boundaries_are_inclusive(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(
            received_from="2025-01-02",
            received_to="2025-01-02",
        ),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
    for compiled in (count_compiled, item_compiled):
        sql = str(compiled)
        assert "planning_applications.received_date >=" in sql
        assert "planning_applications.received_date <=" in sql
        assert date(2025, 1, 2) in compiled.params.values()


def test_nearby_combines_date_status_and_decision_filters(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(
            received_from="2025-01-01",
            received_to="2025-01-31",
            application_status="Decided",
            decision="Granted",
            category="commercial",
        ),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
    predicates = (
        "planning_applications.received_date >=",
        "planning_applications.received_date <=",
        "planning_applications.application_status =",
        "planning_applications.decision =",
        "planning_applications.category =",
    )
    expected_values = {
        date(2025, 1, 1),
        date(2025, 1, 31),
        "Decided",
        "Granted",
        "commercial",
    }
    for compiled in (count_compiled, item_compiled):
        sql = str(compiled)
        assert all(predicate in sql for predicate in predicates)
        assert expected_values.issubset(set(compiled.params.values()))


def test_nearby_combines_relevance_filters_with_spatial_radius(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(
            application_status="Decided",
            category="commercial",
        ),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
    for compiled in (count_compiled, item_compiled):
        sql = str(compiled)
        assert "ST_DWithin" in sql
        assert "planning_applications.application_status =" in sql
        assert "planning_applications.category =" in sql
        assert " AND " in sql


def test_nearby_combines_recent_cutoff_with_spatial_and_category_filters(
    nearby_client,
    monkeypatch: pytest.MonkeyPatch,
):
    client, session = nearby_client
    monkeypatch.setattr(
        planning_applications,
        "_current_utc_date",
        lambda: date(2025, 2, 1),
    )

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(recent_days=30, category="commercial"),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
    for compiled in (count_compiled, item_compiled):
        sql = str(compiled)
        assert "ST_DWithin" in sql
        assert "planning_applications.received_date >=" in sql
        assert "planning_applications.category =" in sql
        assert date(2025, 1, 2) in compiled.params.values()


def test_nearby_filtered_total_is_before_pagination(nearby_client):
    client, session = nearby_client
    session.scalar.return_value = 8
    session.execute.return_value.all.return_value = [
        (_application(identifier=1, source_object_id=101), 1.25),
    ]

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(
            category="commercial",
            limit=1,
            offset=3,
        ),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 8
    assert len(response.json()["items"]) == 1
    count_compiled, item_compiled = _compiled_statements(session)
    count_sql = str(count_compiled).upper()
    item_sql = str(item_compiled).upper()
    assert "PLANNING_APPLICATIONS.CATEGORY =" in count_sql
    assert "LIMIT" not in count_sql
    assert "OFFSET" not in count_sql
    assert "LIMIT" in item_sql
    assert "OFFSET" in item_sql


def test_nearby_without_relevance_filters_keeps_radius_only(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(),
    )

    assert response.status_code == 200
    count_compiled, _ = _compiled_statements(session)
    count_sql = str(count_compiled)
    assert "ST_DWithin" in count_sql
    assert "planning_applications.received_date" not in count_sql
    assert "planning_applications.application_status" not in count_sql
    assert "planning_applications.decision" not in count_sql
    assert "planning_applications.category" not in count_sql


def test_nearby_rejects_invalid_category(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(category="agricultural"),
    )

    assert response.status_code == 422
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


def test_nearby_builds_postgis_geography_queries(nearby_client):
    client, session = nearby_client

    response = client.get(
        "/api/v1/planning-applications/nearby",
        params=_valid_params(radius_km=7.5, limit=12, offset=4),
    )

    assert response.status_code == 200
    count_compiled, item_compiled = _compiled_statements(session)
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
