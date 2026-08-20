from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import dependencies
from backend.app.dependencies import get_db
from backend.app.main import app


PLANNING_APPLICATION_ROWS = [
    {
        "id": 1,
        "source_object_id": 1001,
        "planning_authority": "Cork City Council",
        "application_number": "174041",
        "application_status": "Decided",
        "decision": "GRANT",
        "received_date": "2024-01-10",
    },
    {
        "id": 2,
        "source_object_id": 1002,
        "planning_authority": "Cork City Council",
        "application_number": "174041",
        "application_status": "Pending",
        "decision": None,
        "received_date": "2024-01-15",
    },
    {
        "id": 3,
        "source_object_id": 1003,
        "planning_authority": "Dublin City Council",
        "application_number": "DCC-1",
        "application_status": "Decided",
        "decision": "REFUSE",
        "received_date": "2024-02-01",
    },
    {
        "id": 4,
        "source_object_id": 1004,
        "planning_authority": "Galway City Council",
        "application_number": "GCC-1",
        "application_status": "Decided",
        "decision": "GRANT",
        "received_date": "2024-02-01",
    },
    {
        "id": 5,
        "source_object_id": 1005,
        "planning_authority": "Cork City Council",
        "application_number": "CORK-5",
        "application_status": "Decided",
        "decision": "GRANT",
        "received_date": "2024-03-01",
    },
    {
        "id": 6,
        "source_object_id": 1006,
        "planning_authority": "Cork City Council",
        "application_number": "CORK-6",
        "application_status": "Decided",
        "decision": "GRANT",
        "received_date": "2023-12-31",
    },
]


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE planning_applications (
                    id INTEGER PRIMARY KEY,
                    source_object_id INTEGER NOT NULL UNIQUE,
                    planning_authority VARCHAR NOT NULL,
                    application_number VARCHAR NOT NULL,
                    description TEXT,
                    address TEXT,
                    postcode VARCHAR,
                    application_status VARCHAR,
                    application_type VARCHAR,
                    decision VARCHAR,
                    received_date DATE,
                    decision_date DATE,
                    grant_date DATE,
                    number_residential_units INTEGER,
                    floor_area FLOAT,
                    application_url TEXT,
                    location TEXT,
                    source_updated_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO planning_applications (
                    id,
                    source_object_id,
                    planning_authority,
                    application_number,
                    application_status,
                    decision,
                    received_date
                ) VALUES (
                    :id,
                    :source_object_id,
                    :planning_authority,
                    :application_number,
                    :application_status,
                    :decision,
                    :received_date
                )
                """
            ),
            PLANNING_APPLICATION_ROWS,
        )

    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _item_ids(response_data: dict) -> list[int]:
    return [item["id"] for item in response_data["items"]]


def test_default_pagination_and_response_structure(client: TestClient) -> None:
    response = client.get("/api/v1/planning-applications")

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"items", "limit", "offset", "total"}
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert data["total"] == 6
    assert _item_ids(data) == [5, 4, 3, 2, 1, 6]
    assert "source_object_id" in data["items"][0]
    assert "created_at" not in data["items"][0]
    assert "updated_at" not in data["items"][0]
    assert "location" not in data["items"][0]


def test_custom_limit_and_offset(client: TestClient) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert data["total"] == 6
    assert _item_ids(data) == [4, 3]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ],
)
def test_pagination_validation(client: TestClient, params: dict) -> None:
    response = client.get("/api/v1/planning-applications", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("parameter", "value", "expected_ids"),
    [
        ("planning_authority", "Cork City Council", [5, 2, 1, 6]),
        ("application_status", "Pending", [2]),
        ("decision", "REFUSE", [3]),
        ("received_from", "2024-02-01", [5, 4, 3]),
        ("received_to", "2024-01-15", [2, 1, 6]),
    ],
)
def test_individual_filters(
    client: TestClient,
    parameter: str,
    value: str,
    expected_ids: list[int],
) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={parameter: value},
    )

    assert response.status_code == 200
    data = response.json()
    assert _item_ids(data) == expected_ids
    assert data["total"] == len(expected_ids)


def test_combined_filters(client: TestClient) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={
            "planning_authority": "Cork City Council",
            "application_status": "Decided",
            "decision": "GRANT",
            "received_from": "2024-01-01",
            "received_to": "2024-03-01",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert _item_ids(data) == [5, 1]
    assert data["total"] == 2


def test_date_boundaries_are_inclusive(client: TestClient) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={
            "received_from": "2024-02-01",
            "received_to": "2024-02-01",
        },
    )

    assert response.status_code == 200
    assert _item_ids(response.json()) == [4, 3]


def test_ordering_is_deterministic(client: TestClient) -> None:
    response = client.get("/api/v1/planning-applications")

    assert response.status_code == 200
    assert _item_ids(response.json()) == [5, 4, 3, 2, 1, 6]


def test_filtered_total_is_calculated_before_pagination(client: TestClient) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={
            "planning_authority": "Cork City Council",
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 1
    assert _item_ids(data) == [2]


def test_empty_results(client: TestClient) -> None:
    response = client.get(
        "/api/v1/planning-applications",
        params={"planning_authority": "Missing Authority"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 20,
        "offset": 0,
        "total": 0,
    }


def test_database_dependency_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock()
    session_factory = Mock(return_value=session)
    monkeypatch.setattr(dependencies, "SessionLocal", session_factory)

    dependency = dependencies.get_db()
    assert next(dependency) is session
    dependency.close()

    session_factory.assert_called_once_with()
    session.close.assert_called_once_with()
