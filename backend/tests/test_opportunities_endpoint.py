from datetime import date, timedelta
from unittest.mock import Mock, call

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.api import opportunities
from backend.app.dependencies import get_db
from backend.app.main import app
from backend.app.services.opportunity_scorer import (
    SCORE_COMPONENT_MAXIMUMS,
    OpportunityScoreBreakdown,
    OpportunityScoreComponent,
    OpportunityScoreResult,
    opportunity_level_for_score,
)


CURRENT_DATE = date(2026, 8, 23)


def _candidate_row(
    identifier: int,
    *,
    application_number: str | None = None,
    planning_authority: str = "Kerry County Council",
    description: str | None = "Construction of a commercial building.",
    address: str | None = "1 Main Street",
    application_type: str | None = "Permission",
    application_status: str | None = "Pending",
    decision: str | None = None,
    received_date: date | None = CURRENT_DATE,
    application_url: str | None = "https://example.test/planning",
    category: str = "commercial",
    number_residential_units: int | None = None,
    floor_area: float | None = 500.0,
    distance_km: float = 2.5,
) -> dict:
    return {
        "id": identifier,
        "application_number": application_number or f"APP-{identifier}",
        "planning_authority": planning_authority,
        "description": description,
        "address": address,
        "application_type": application_type,
        "application_status": application_status,
        "decision": decision,
        "received_date": received_date,
        "application_url": application_url,
        "category": category,
        "number_residential_units": number_residential_units,
        "floor_area": floor_area,
        "distance_km": distance_km,
    }


def _score_result(score: int) -> OpportunityScoreResult:
    remaining = score
    components = []
    for maximum in (30, 30, 20, 10, 10):
        component = min(remaining, maximum)
        components.append(component)
        remaining -= component
    return OpportunityScoreResult(
        opportunity_score=score,
        opportunity_level=opportunity_level_for_score(score),
        score_breakdown=OpportunityScoreBreakdown(*components),
        score_components=tuple(
            OpportunityScoreComponent(
                name=name,
                points_awarded=points,
                maximum_points=SCORE_COMPONENT_MAXIMUMS[name],
                explanation="Test scoring evidence.",
            )
            for name, points in zip(SCORE_COMPONENT_MAXIMUMS, components)
        ),
        reasons=("Test evidence",),
    )


def _set_candidate_rows(session: Mock, rows: list[dict]) -> None:
    session.execute.return_value.mappings.return_value.all.return_value = rows


def _compiled_candidate_statement(session: Mock):
    statement = session.execute.call_args.args[0]
    return statement.compile(dialect=postgresql.dialect())


def _compiled_count_statement(session: Mock):
    statement = session.scalar.call_args.args[0]
    return statement.compile(dialect=postgresql.dialect())


@pytest.fixture
def opportunity_client(monkeypatch: pytest.MonkeyPatch):
    session = Mock(spec=Session)
    _set_candidate_rows(session, [])
    session.scalar.return_value = 0
    session.scalars.return_value.all.return_value = []
    monkeypatch.setattr(
        opportunities,
        "_current_utc_date",
        lambda: CURRENT_DATE,
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.clear()


def _valid_params(**overrides) -> dict:
    params = {
        "latitude": 52.2704,
        "longitude": -9.7026,
    }
    params.update(overrides)
    return params


def test_default_feed_contract_and_empty_result(opportunity_client) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "total_pages": 0,
    }
    session.execute.assert_called_once()
    session.scalar.assert_not_called()


def test_candidate_query_uses_postgis_radius_and_recent_cutoff(
    opportunity_client,
) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    compiled = _compiled_candidate_statement(session)
    sql = str(compiled)
    assert "ST_DWithin" in sql
    assert "ST_Distance" in sql
    assert "ST_SetSRID" in sql
    assert "ST_MakePoint" in sql
    assert "geography(POINT,4326)" in sql
    assert "planning_applications.received_date >=" in sql
    assert "planning_applications.category IS NOT NULL" in sql
    assert date(2026, 7, 24) in compiled.params.values()
    assert 25000.0 in compiled.params.values()


def test_best_query_scores_the_complete_filtered_set_before_paging(
    opportunity_client,
) -> None:
    client, session = opportunity_client

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(page=2, page_size=100),
    )

    assert response.status_code == 200
    compiled = _compiled_candidate_statement(session)
    sql = str(compiled)
    assert "ORDER BY" not in sql
    assert "LIMIT" not in sql
    assert "OFFSET" not in sql
    session.scalar.assert_not_called()


@pytest.mark.parametrize(
    ("sort", "primary_order"),
    [
        ("nearest", "distance_km ASC"),
        ("newest", "planning_applications.received_date DESC"),
    ],
)
def test_database_sorted_modes_are_globally_ordered_and_paginated(
    opportunity_client,
    sort: str,
    primary_order: str,
) -> None:
    client, session = opportunity_client
    session.scalar.return_value = 45

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(sort=sort, page=2, page_size=20),
    )

    assert response.status_code == 200
    compiled = _compiled_candidate_statement(session)
    sql = str(compiled)
    assert primary_order in sql
    assert "planning_applications.received_date DESC" in sql
    assert "planning_applications.id DESC" in sql
    assert sql.index(primary_order) < sql.index("planning_applications.id DESC")
    if sort == "nearest":
        assert sql.index(primary_order) < sql.index(
            "planning_applications.received_date DESC"
        )
        assert sql.index("planning_applications.received_date DESC") < sql.index(
            "planning_applications.id DESC"
        )
    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert 20 in compiled.params.values()
    assert response.json() == {
        "items": [],
        "page": 2,
        "page_size": 20,
        "total": 45,
        "total_pages": 3,
    }

    count_sql = str(_compiled_count_statement(session))
    assert "count(" in count_sql.lower()
    assert "ST_DWithin" in count_sql
    assert "ORDER BY" not in count_sql


def test_optional_category_filter_is_applied_in_sql(opportunity_client) -> None:
    client, session = opportunity_client

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(category="industrial"),
    )

    assert response.status_code == 200
    compiled = _compiled_candidate_statement(session)
    assert "planning_applications.category =" in str(compiled)
    assert "industrial" in compiled.params.values()


def test_non_actionable_statuses_are_excluded_exactly_in_sql(
    opportunity_client,
) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    compiled = _compiled_candidate_statement(session)
    sql = str(compiled)
    assert "planning_applications.application_status IS NULL" in sql
    assert "planning_applications.application_status NOT IN" in sql
    assert "LIKE" not in sql.upper()
    assert "LOWER" not in sql.upper()
    status_parameters = [
        value
        for value in compiled.params.values()
        if isinstance(value, (list, tuple))
    ]
    assert status_parameters == [
        list(opportunities.EXCLUDED_OPPORTUNITY_APPLICATION_STATUSES)
    ]


def test_normal_project_statuses_are_not_in_exact_exclusion_list() -> None:
    normal_statuses = {
        "Pending",
        "Decided",
        "NEW APPLICATION",
        "APPLICATION FINALISED",
        "FURTHER INFORMATION",
        "APPEALED",
    }

    assert normal_statuses.isdisjoint(
        opportunities.EXCLUDED_OPPORTUNITY_APPLICATION_STATUSES
    )
    assert set(opportunities.EXCLUDED_OPPORTUNITY_APPLICATION_STATUSES) == {
        "Invalid - Case Closed",
        "Application Invalid",
        "INCOMPLETED APPLICATION",
        "WITHDRAWN",
    }


def test_candidate_query_selects_only_response_and_scorer_fields(
    opportunity_client,
) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    sql = str(_compiled_candidate_statement(session))
    for column_name in (
        "id",
        "application_number",
        "planning_authority",
        "description",
        "address",
        "application_type",
        "application_status",
        "decision",
        "received_date",
        "application_url",
        "category",
        "number_residential_units",
        "floor_area",
    ):
        assert column_name in sql
    for excluded_column in (
        "source_object_id",
        "postcode",
        "decision_date",
        "grant_date",
        "source_updated_at",
        "created_at",
        "updated_at",
    ):
        assert excluded_column not in sql


def test_only_loaded_candidates_are_scored_with_exact_inputs_and_date(
    opportunity_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = opportunity_client
    rows = [
        _candidate_row(
            1,
            description="Construction of an industrial facility.",
            application_type="Permission Consequent",
            received_date=date(2026, 8, 20),
            category="industrial",
            number_residential_units=2,
            floor_area=2500.5,
        ),
        _candidate_row(
            2,
            description="Erect signage.",
            application_type="Permission",
            received_date=date(2026, 8, 22),
            category="commercial",
            number_residential_units=None,
            floor_area=20.0,
        ),
    ]
    _set_candidate_rows(session, rows)
    scorer = Mock(side_effect=[_score_result(80), _score_result(20)])
    monkeypatch.setattr(
        opportunities,
        "score_planning_application_opportunity",
        scorer,
    )

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    assert scorer.call_args_list == [
        call(
            description="Construction of an industrial facility.",
            application_type="Permission Consequent",
            number_residential_units=2,
            floor_area=2500.5,
            received_date=date(2026, 8, 20),
            category="industrial",
            current_date=CURRENT_DATE,
        ),
        call(
            description="Erect signage.",
            application_type="Permission",
            number_residential_units=None,
            floor_area=20.0,
            received_date=date(2026, 8, 22),
            category="commercial",
            current_date=CURRENT_DATE,
        ),
    ]
    assert len(scorer.call_args_list) == len(rows)


def test_best_sort_and_page_are_applied_after_all_candidates_are_scored(
    opportunity_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = opportunity_client
    rows = [
        _candidate_row(1),
        _candidate_row(2),
        _candidate_row(3),
        _candidate_row(4),
    ]
    _set_candidate_rows(session, rows)
    scorer = Mock(
        side_effect=[
            _score_result(40),
            _score_result(90),
            _score_result(60),
            _score_result(80),
        ]
    )
    monkeypatch.setattr(
        opportunities,
        "score_planning_application_opportunity",
        scorer,
    )

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(page=2, page_size=2),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [3, 1]
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert payload["total"] == 4
    assert payload["total_pages"] == 2
    assert scorer.call_count == 4


def test_equal_scores_use_received_date_then_id_descending(
    opportunity_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session = opportunity_client
    rows = [
        _candidate_row(1, received_date=CURRENT_DATE - timedelta(days=1)),
        _candidate_row(2, received_date=CURRENT_DATE),
        _candidate_row(3, received_date=CURRENT_DATE),
    ]
    _set_candidate_rows(session, rows)
    monkeypatch.setattr(
        opportunities,
        "score_planning_application_opportunity",
        Mock(return_value=_score_result(60)),
    )

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [3, 2, 1]


def test_explicit_page_and_page_size_return_correct_metadata(
    opportunity_client,
) -> None:
    client, session = opportunity_client
    _set_candidate_rows(
        session,
        [_candidate_row(identifier) for identifier in range(1, 26)],
    )

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(page=2, page_size=10),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == list(range(15, 5, -1))
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["total"] == 25
    assert payload["total_pages"] == 3


def test_strong_older_electrical_project_ranks_above_newer_minor_signage(
    opportunity_client,
) -> None:
    client, session = opportunity_client
    _set_candidate_rows(
        session,
        [
            _candidate_row(
                10,
                description="ERECT SIGNAGE TO FRONT OF EXISTING OFFICE",
                received_date=CURRENT_DATE,
                category="commercial",
                floor_area=50.0,
                distance_km=1.0,
            ),
            _candidate_row(
                20,
                description=(
                    "Construction of a new industrial manufacturing facility "
                    "with explicit electrical infrastructure."
                ),
                received_date=CURRENT_DATE - timedelta(days=10),
                category="industrial",
                floor_area=2500.0,
                distance_km=4.25,
            ),
        ],
    )

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [20, 10]
    assert payload["items"][0]["opportunity_score"] > payload["items"][1][
        "opportunity_score"
    ]
    assert payload["items"][0]["distance_km"] == 4.25
    assert payload["items"][0]["opportunity_breakdown"] == {
        "project_scope": 30,
        "electrical_relevance": 30,
        "project_scale": 16,
        "lead_timing": 10,
        "category_fit": 10,
    }
    components = {
        component["name"]: component
        for component in payload["items"][0]["opportunity_score_components"]
    }
    assert components["project_scope"] == {
        "name": "project_scope",
        "points_awarded": 30,
        "maximum_points": 30,
        "explanation": "New industrial development indicators were identified.",
    }
    assert components["electrical_relevance"] == {
        "name": "electrical_relevance",
        "points_awarded": 30,
        "maximum_points": 30,
        "explanation": (
            'The planning description includes "electrical infrastructure", '
            "a strong electrical indicator."
        ),
    }
    assert payload["items"][1]["opportunity_breakdown"]["project_scope"] == 5
    assert payload["items"][1]["opportunity_breakdown"][
        "electrical_relevance"
    ] == 0
    assert payload["items"][1]["opportunity_score_components"][1] == {
        "name": "electrical_relevance",
        "points_awarded": 0,
        "maximum_points": 30,
        "explanation": "No qualifying electrical work indicators were identified.",
    }


def test_response_exposes_only_feed_fields(opportunity_client) -> None:
    client, session = opportunity_client
    _set_candidate_rows(session, [_candidate_row(1)])

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    assert set(response.json()["items"][0]) == {
        "id",
        "application_number",
        "planning_authority",
        "description",
        "address",
        "application_type",
        "application_status",
        "decision",
        "received_date",
        "application_url",
        "category",
        "distance_km",
        "opportunity_score",
        "opportunity_level",
        "opportunity_breakdown",
        "opportunity_score_components",
    }


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": -90.01},
        {"latitude": 90.01},
        {"longitude": -180.01},
        {"longitude": 180.01},
        {"radius_km": 0},
        {"radius_km": -1},
        {"radius_km": 50.01},
        {"recent_days": 0},
        {"recent_days": -1},
        {"recent_days": 366},
        {"recent_days": "not-an-integer"},
        {"page": 0},
        {"page": -1},
        {"page": "not-an-integer"},
        {"page_size": 0},
        {"page_size": -1},
        {"page_size": 101},
        {"page_size": "not-an-integer"},
        {"sort": "furthest"},
        {"category": "agricultural"},
    ],
)
def test_invalid_query_parameters_return_422_without_querying(
    opportunity_client,
    params: dict,
) -> None:
    client, session = opportunity_client

    response = client.get(
        "/api/v1/opportunities",
        params=_valid_params(**params),
    )

    assert response.status_code == 422
    session.execute.assert_not_called()


def test_latitude_and_longitude_are_required(opportunity_client) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/opportunities")

    assert response.status_code == 422
    session.execute.assert_not_called()


def test_endpoint_is_read_only(opportunity_client) -> None:
    client, session = opportunity_client
    _set_candidate_rows(session, [_candidate_row(1)])

    response = client.get("/api/v1/opportunities", params=_valid_params())

    assert response.status_code == 200
    session.execute.assert_called_once()
    session.scalar.assert_not_called()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_existing_planning_listing_remains_available(opportunity_client) -> None:
    client, session = opportunity_client

    response = client.get("/api/v1/planning-applications")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 20,
        "offset": 0,
        "total": 0,
    }
    session.scalar.assert_called_once()
    session.scalars.assert_called_once()
