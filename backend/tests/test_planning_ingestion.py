from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from backend.app.models import PlanningApplication
from backend.app.services import planning_ingestion


def _transformed_application(
    source_object_id: int,
    planning_authority: str = "Carlow County Council",
) -> dict:
    return {
        "source_object_id": source_object_id,
        "planning_authority": planning_authority,
        "application_number": f"24/{source_object_id}",
        "description": "Construction of a dwelling.",
        "address": "Main Street, Carlow",
        "postcode": "R93 ABC1",
        "application_status": "Decided",
        "application_type": "Permission",
        "decision": "Granted",
        "received_date": None,
        "decision_date": None,
        "grant_date": None,
        "number_residential_units": 1,
        "floor_area": 120.5,
        "application_url": "https://example.test/application",
        "location": None,
        "source_updated_at": None,
    }


def test_new_application_is_inserted(monkeypatch: pytest.MonkeyPatch) -> None:
    features = [{"properties": {"OBJECTID": 101}}]
    fetch = Mock(return_value=features)
    transform = Mock(return_value=_transformed_application(101))
    monkeypatch.setattr(planning_ingestion, "fetch_planning_applications", fetch)
    monkeypatch.setattr(planning_ingestion, "transform_planning_application", transform)
    session = Mock(spec=Session)
    session.scalar.return_value = None

    result = planning_ingestion.ingest_planning_applications(session, limit=7)

    assert result == {"fetched": 1, "inserted": 1, "updated": 0}
    fetch.assert_called_once_with(7)
    transform.assert_called_once_with(features[0])
    session.add.assert_called_once()
    inserted = session.add.call_args.args[0]
    assert isinstance(inserted, PlanningApplication)
    assert inserted.source_object_id == 101
    assert inserted.planning_authority == "Carlow County Council"
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_existing_application_is_updated_without_duplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = {"properties": {"OBJECTID": 202}}
    existing = PlanningApplication(
        id=12,
        source_object_id=202,
        planning_authority="Old Authority",
        application_number="old-number",
    )
    original_created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    original_updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    existing.created_at = original_created_at
    existing.updated_at = original_updated_at
    transformed = {
        **_transformed_application(202, "Updated Authority"),
        "id": 999,
        "created_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(
        planning_ingestion,
        "fetch_planning_applications",
        Mock(return_value=[feature]),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(return_value=transformed),
    )
    session = Mock(spec=Session)
    session.scalar.return_value = existing

    result = planning_ingestion.ingest_planning_applications(session)

    assert result == {"fetched": 1, "inserted": 0, "updated": 1}
    assert existing.planning_authority == "Updated Authority"
    assert existing.application_number == "24/202"
    assert existing.id == 12
    assert existing.created_at is original_created_at
    assert existing.updated_at is original_updated_at
    session.add.assert_not_called()
    session.commit.assert_called_once_with()


def test_mixed_batch_reports_inserted_and_updated_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = [
        {"properties": {"OBJECTID": 301}},
        {"properties": {"OBJECTID": 302}},
    ]
    existing = PlanningApplication(
        source_object_id=302,
        planning_authority="Old Authority",
        application_number="old-number",
    )
    monkeypatch.setattr(
        planning_ingestion,
        "fetch_planning_applications",
        Mock(return_value=features),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(301),
                _transformed_application(302, "Updated Authority"),
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [None, existing]

    result = planning_ingestion.ingest_planning_applications(session, limit=2)

    assert result == {"fetched": 2, "inserted": 1, "updated": 1}
    assert existing.planning_authority == "Updated Authority"
    session.add.assert_called_once()
    assert session.scalar.call_count == 2
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_repeated_source_id_does_not_create_duplicate_pending_inserts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = [
        {"properties": {"OBJECTID": 401}},
        {"properties": {"OBJECTID": 401}},
    ]
    monkeypatch.setattr(
        planning_ingestion,
        "fetch_planning_applications",
        Mock(return_value=features),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(401, "First Authority"),
                _transformed_application(401, "Latest Authority"),
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.return_value = None

    result = planning_ingestion.ingest_planning_applications(session)

    assert result == {"fetched": 2, "inserted": 1, "updated": 0}
    session.scalar.assert_called_once()
    session.add.assert_called_once()
    inserted = session.add.call_args.args[0]
    assert inserted.planning_authority == "Latest Authority"


def test_transformation_failure_rolls_back_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = [
        {"properties": {"OBJECTID": 501}},
        {"properties": {"OBJECTID": 502}},
    ]
    failure = ValueError("invalid source feature")
    monkeypatch.setattr(
        planning_ingestion,
        "fetch_planning_applications",
        Mock(return_value=features),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(side_effect=[_transformed_application(501), failure]),
    )
    session = Mock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError) as exc_info:
        planning_ingestion.ingest_planning_applications(session)

    assert exc_info.value is failure
    session.add.assert_called_once()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_database_failure_rolls_back_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    feature = {"properties": {"OBJECTID": 601}}
    failure = RuntimeError("database unavailable")
    monkeypatch.setattr(
        planning_ingestion,
        "fetch_planning_applications",
        Mock(return_value=[feature]),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(return_value=_transformed_application(601)),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = failure

    with pytest.raises(RuntimeError) as exc_info:
        planning_ingestion.ingest_planning_applications(session)

    assert exc_info.value is failure
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_successful_empty_batch_commits_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fetch = Mock(return_value=[])
    transform = Mock()
    monkeypatch.setattr(planning_ingestion, "fetch_planning_applications", fetch)
    monkeypatch.setattr(planning_ingestion, "transform_planning_application", transform)
    session = Mock(spec=Session)

    result = planning_ingestion.ingest_planning_applications(session, limit=25)

    assert result == {"fetched": 0, "inserted": 0, "updated": 0}
    fetch.assert_called_once_with(25)
    transform.assert_not_called()
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
