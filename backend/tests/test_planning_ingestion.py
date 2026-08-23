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
        "category": "residential",
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
    assert inserted.category == "residential"
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
        category="energy",
    )
    original_created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    original_updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    existing.created_at = original_created_at
    existing.updated_at = original_updated_at
    transformed = {
        **_transformed_application(202, "Updated Authority"),
        "description": "Construction of a retail shop.",
        "number_residential_units": 0,
        "category": "commercial",
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
    assert existing.category == "commercial"
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


def test_distinct_source_ids_can_share_authority_and_application_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = [
        {"properties": {"OBJECTID": 21787}},
        {"properties": {"OBJECTID": 21788}},
    ]
    shared_source_values = {
        "planning_authority": "Cork City Council",
        "application_number": "174041",
    }
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
                {
                    **_transformed_application(21787),
                    **shared_source_values,
                },
                {
                    **_transformed_application(21788),
                    **shared_source_values,
                },
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [None, None]

    result = planning_ingestion.ingest_planning_applications(session, limit=2)

    assert result == {"fetched": 2, "inserted": 2, "updated": 0}
    inserted = [call.args[0] for call in session.add.call_args_list]
    assert [application.source_object_id for application in inserted] == [
        21787,
        21788,
    ]
    assert all(
        application.planning_authority == "Cork City Council"
        and application.application_number == "174041"
        for application in inserted
    )
    session.commit.assert_called_once_with()


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


def test_all_ingestion_processes_pages_and_aggregates_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        [
            {"properties": {"OBJECTID": 701}},
            {"properties": {"OBJECTID": 702}},
        ],
        [{"properties": {"OBJECTID": 703}}],
    ]
    existing = PlanningApplication(
        source_object_id=702,
        planning_authority="Old Authority",
        application_number="old-number",
    )
    page_iterator = Mock(return_value=iter(pages))
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages",
        page_iterator,
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(701),
                _transformed_application(702, "Updated Authority"),
                _transformed_application(703),
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [None, existing, None]

    result = planning_ingestion.ingest_all_planning_applications(
        session,
        page_size=250,
        max_pages=None,
    )

    assert result == {
        "pages_processed": 2,
        "fetched": 3,
        "inserted": 2,
        "updated": 1,
    }
    page_iterator.assert_called_once_with(250)
    assert existing.planning_authority == "Updated Authority"
    assert session.add.call_count == 2
    assert session.commit.call_count == 2
    session.rollback.assert_not_called()


def test_later_page_failure_rolls_back_only_current_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        [{"properties": {"OBJECTID": 801}}],
        [
            {"properties": {"OBJECTID": 802}},
            {"properties": {"OBJECTID": 803}},
        ],
    ]
    failure = ValueError("invalid later-page feature")
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages",
        Mock(return_value=iter(pages)),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(801),
                _transformed_application(802),
                failure,
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError) as exc_info:
        planning_ingestion.ingest_all_planning_applications(session)

    assert exc_info.value is failure
    assert session.commit.call_count == 1
    session.rollback.assert_called_once_with()
    method_names = [method_call[0] for method_call in session.method_calls]
    assert method_names.index("commit") < method_names.index("rollback")


def test_pages_are_processed_without_collecting_iterator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    session.scalar.return_value = None

    def lazy_pages():
        yield [{"properties": {"OBJECTID": 901}}]
        assert session.commit.call_count == 1
        yield [{"properties": {"OBJECTID": 902}}]

    page_iterator = Mock(return_value=lazy_pages())
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages",
        page_iterator,
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(901),
                _transformed_application(902),
            ]
        ),
    )

    result = planning_ingestion.ingest_all_planning_applications(session)

    assert result == {
        "pages_processed": 2,
        "fetched": 2,
        "inserted": 2,
        "updated": 0,
    }
    page_iterator.assert_called_once_with(500)
    assert session.commit.call_count == 2


def test_max_pages_limits_processing_without_consuming_another_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumed_source_ids = []

    def lazy_pages():
        for source_object_id in [1001, 1002, 1003]:
            consumed_source_ids.append(source_object_id)
            yield [{"properties": {"OBJECTID": source_object_id}}]

    page_iterator = Mock(return_value=lazy_pages())
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages",
        page_iterator,
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(1001),
                _transformed_application(1002),
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.return_value = None

    result = planning_ingestion.ingest_all_planning_applications(
        session,
        max_pages=2,
    )

    assert result == {
        "pages_processed": 2,
        "fetched": 2,
        "inserted": 2,
        "updated": 0,
    }
    assert consumed_source_ids == [1001, 1002]
    assert session.commit.call_count == 2
    page_iterator.assert_called_once_with(500)


@pytest.mark.parametrize("max_pages", [0, -1, True, 1.5, "2", []])
def test_invalid_max_pages_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    max_pages: object,
) -> None:
    page_iterator = Mock()
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages",
        page_iterator,
    )
    session = Mock(spec=Session)

    with pytest.raises(ValueError, match="positive integer"):
        planning_ingestion.ingest_all_planning_applications(
            session,
            max_pages=max_pages,
        )

    page_iterator.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_sync_uses_max_watermark_and_aggregates_page_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watermark = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    boundary_feature = {
        "properties": {
            "OBJECTID": 1101,
            "ETL_DATE": int(watermark.timestamp() * 1000),
        }
    }
    pages = [
        [boundary_feature, {"properties": {"OBJECTID": 1102}}],
        [{"properties": {"OBJECTID": 1103}}],
    ]
    existing = PlanningApplication(
        source_object_id=1102,
        planning_authority="Old Authority",
        application_number="old-number",
        category="residential",
    )
    filtered_iterator = Mock(return_value=iter(pages))
    transform = Mock(
        side_effect=[
            {
                **_transformed_application(1101),
                "source_updated_at": watermark,
            },
            {
                **_transformed_application(1102, "Updated Authority"),
                "description": "Development of a solar farm.",
                "number_residential_units": 0,
                "category": "energy",
            },
            _transformed_application(1103),
        ]
    )
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages_since",
        filtered_iterator,
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        transform,
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [watermark, None, existing, None]

    result = planning_ingestion.sync_planning_applications(
        session,
        page_size=200,
    )

    assert result == {
        "watermark": watermark,
        "pages_processed": 2,
        "fetched": 3,
        "inserted": 2,
        "updated": 1,
    }
    watermark_statement = session.scalar.call_args_list[0].args[0]
    compiled_statement = str(watermark_statement.compile()).lower()
    assert "max(planning_applications.source_updated_at)" in compiled_statement
    filtered_iterator.assert_called_once_with(watermark, 200)
    transform.assert_any_call(boundary_feature)
    assert existing.planning_authority == "Updated Authority"
    assert existing.category == "energy"
    assert session.add.call_count == 2
    assert all(
        call.args[0].category is not None
        for call in session.add.call_args_list
    )
    assert session.commit.call_count == 2
    session.rollback.assert_not_called()


def test_sync_later_page_failure_rolls_back_current_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watermark = datetime(2024, 6, 1, tzinfo=timezone.utc)
    pages = [
        [{"properties": {"OBJECTID": 1201}}],
        [{"properties": {"OBJECTID": 1202}}],
    ]
    failure = ValueError("invalid filtered feature")
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages_since",
        Mock(return_value=iter(pages)),
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(side_effect=[_transformed_application(1201), failure]),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [watermark, None]

    with pytest.raises(ValueError) as exc_info:
        planning_ingestion.sync_planning_applications(session)

    assert exc_info.value is failure
    assert session.commit.call_count == 1
    session.rollback.assert_called_once_with()
    method_names = [method_call[0] for method_call in session.method_calls]
    assert method_names.index("commit") < method_names.index("rollback")


def test_sync_max_pages_does_not_consume_another_filtered_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    watermark = datetime(2024, 6, 1, tzinfo=timezone.utc)
    consumed_source_ids = []

    def lazy_pages():
        for source_object_id in [1301, 1302, 1303]:
            consumed_source_ids.append(source_object_id)
            yield [{"properties": {"OBJECTID": source_object_id}}]

    filtered_iterator = Mock(return_value=lazy_pages())
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages_since",
        filtered_iterator,
    )
    monkeypatch.setattr(
        planning_ingestion,
        "transform_planning_application",
        Mock(
            side_effect=[
                _transformed_application(1301),
                _transformed_application(1302),
            ]
        ),
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [watermark, None, None]

    result = planning_ingestion.sync_planning_applications(
        session,
        max_pages=2,
    )

    assert result == {
        "watermark": watermark,
        "pages_processed": 2,
        "fetched": 2,
        "inserted": 2,
        "updated": 0,
    }
    assert consumed_source_ids == [1301, 1302]
    assert session.commit.call_count == 2
    filtered_iterator.assert_called_once_with(watermark, 500)


def test_sync_without_watermark_requires_initial_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filtered_iterator = Mock()
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages_since",
        filtered_iterator,
    )
    session = Mock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(
        planning_ingestion.InitialPlanningImportRequiredError,
        match="initial import",
    ):
        planning_ingestion.sync_planning_applications(session)

    filtered_iterator.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_sync_rejects_invalid_max_pages_before_querying_watermark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filtered_iterator = Mock()
    monkeypatch.setattr(
        planning_ingestion,
        "iter_planning_application_pages_since",
        filtered_iterator,
    )
    session = Mock(spec=Session)

    with pytest.raises(ValueError, match="positive integer"):
        planning_ingestion.sync_planning_applications(session, max_pages=0)

    session.scalar.assert_not_called()
    filtered_iterator.assert_not_called()
