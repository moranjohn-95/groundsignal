from io import StringIO
from unittest.mock import Mock, call

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.commands import backfill_planning_categories as command
from backend.app.models import PlanningApplication
from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
)


def _application(
    identifier: int,
    description: str | None = "Construction of a dwelling.",
    *,
    application_type: str | None = "Permission",
    number_residential_units: int | None = 1,
    floor_area: float | None = 120.0,
    category: str | None = None,
) -> PlanningApplication:
    return PlanningApplication(
        id=identifier,
        description=description,
        application_type=application_type,
        number_residential_units=number_residential_units,
        floor_area=floor_area,
        category=category,
    )


def _category_counts(**overrides: int) -> dict[str, int]:
    counts = {category: 0 for category in PLANNING_APPLICATION_CATEGORIES}
    counts.update(overrides)
    return counts


def test_batch_statement_selects_only_null_categories_in_id_order() -> None:
    compiled = command.build_batch_statement(125).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    assert "planning_applications.category IS NULL" in sql
    assert "ORDER BY planning_applications.id ASC" in sql
    assert "LIMIT" in sql
    assert 125 in compiled.params.values()
    assert "FOR UPDATE" in sql
    assert "SKIP LOCKED" not in sql
    for field in (
        "id",
        "description",
        "application_type",
        "number_residential_units",
        "floor_area",
        "category",
    ):
        assert f"planning_applications.{field}" in sql
    for excluded_field in ("location", "address", "created_at", "updated_at"):
        assert f"planning_applications.{excluded_field}" not in sql


def test_later_batch_uses_primary_key_keyset() -> None:
    compiled = command.build_batch_statement(1000, after_id=42000).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    assert "planning_applications.category IS NULL" in sql
    assert "planning_applications.id >" in sql
    assert "ORDER BY planning_applications.id ASC" in sql
    assert 42000 in compiled.params.values()


def test_remaining_check_uses_an_efficient_null_category_probe() -> None:
    session = Mock(spec=Session)
    session.scalar.return_value = 42

    assert command.has_uncategorised_records(session) is True

    compiled = session.scalar.call_args.args[0].compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)
    assert "planning_applications.category IS NULL" in sql
    assert "ORDER BY planning_applications.id ASC" in sql
    assert "LIMIT" in sql
    assert 1 in compiled.params.values()


def test_classifier_inputs_are_persisted_and_committed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    applications = [
        _application(1),
        _application(
            2,
            "Construction of a solar farm.",
            application_type="Permission Consequent",
            number_residential_units=0,
            floor_area=950.5,
        ),
    ]
    loader = Mock(side_effect=[applications, []])
    monkeypatch.setattr(command, "load_uncategorised_batch", loader)
    classifier = Mock(side_effect=["residential", "energy"])

    result = command.backfill_planning_categories(
        session,
        batch_size=2,
        classifier=classifier,
        output=StringIO(),
    )

    assert classifier.call_args_list == [
        call(
            description="Construction of a dwelling.",
            application_type="Permission",
            number_residential_units=1,
            floor_area=120.0,
        ),
        call(
            description="Construction of a solar farm.",
            application_type="Permission Consequent",
            number_residential_units=0,
            floor_area=950.5,
        ),
    ]
    assert [application.category for application in applications] == [
        "residential",
        "energy",
    ]
    assert loader.call_args_list == [
        call(session, 2, None),
        call(session, 2, 2),
    ]
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    assert result.records_categorised == 2
    assert result.category_counts == _category_counts(residential=1, energy=1)
    assert result.uncategorised_records_remain is False


def test_multiple_batches_commit_independently_and_print_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    loader = Mock(
        side_effect=[
            [_application(1), _application(2)],
            [_application(3)],
            [],
        ]
    )
    monkeypatch.setattr(command, "load_uncategorised_batch", loader)
    classifier = Mock(side_effect=["residential", "commercial", "other"])
    output = StringIO()

    result = command.backfill_planning_categories(
        session,
        batch_size=2,
        classifier=classifier,
        output=output,
    )

    assert result.batches_completed == 2
    assert result.records_categorised == 3
    assert result.category_counts == _category_counts(
        residential=1,
        commercial=1,
        other=1,
    )
    assert session.commit.call_count == 2
    assert session.rollback.call_count == 0
    assert loader.call_args_list == [
        call(session, 2, None),
        call(session, 2, 2),
        call(session, 2, 3),
    ]
    assert output.getvalue().splitlines() == [
        "Batch 1 complete: records categorised=2, total categorised=2",
        "Batch 2 complete: records categorised=1, total categorised=3",
    ]


def test_max_batches_stops_after_committed_limit_and_checks_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    loader = Mock(
        side_effect=[
            [_application(1), _application(2)],
            [_application(3), _application(4)],
        ]
    )
    remaining = Mock(return_value=True)
    monkeypatch.setattr(command, "load_uncategorised_batch", loader)
    monkeypatch.setattr(command, "has_uncategorised_records", remaining)

    result = command.backfill_planning_categories(
        session,
        batch_size=2,
        max_batches=2,
        classifier=Mock(return_value="residential"),
        output=StringIO(),
    )

    assert result.batches_completed == 2
    assert result.records_categorised == 4
    assert result.uncategorised_records_remain is True
    assert session.commit.call_count == 2
    assert loader.call_count == 2
    remaining.assert_called_once_with(session)


def test_failed_batch_rolls_back_without_losing_prior_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    first = _application(1)
    second = _application(2)
    monkeypatch.setattr(
        command,
        "load_uncategorised_batch",
        Mock(side_effect=[[first], [second]]),
    )
    failure = RuntimeError("classifier failed")
    classifier = Mock(side_effect=["residential", failure])
    output = StringIO()

    with pytest.raises(RuntimeError) as exc_info:
        command.backfill_planning_categories(
            session,
            batch_size=1,
            classifier=classifier,
            output=output,
        )

    assert exc_info.value is failure
    assert session.method_calls == [call.commit(), call.rollback()]
    assert first.category == "residential"
    assert "Batch 1 complete" in output.getvalue()
    assert "Batch 2 complete" not in output.getvalue()


def test_commit_failure_rolls_back_current_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    failure = RuntimeError("commit failed")
    session.commit.side_effect = failure
    monkeypatch.setattr(
        command,
        "load_uncategorised_batch",
        Mock(return_value=[_application(1)]),
    )

    with pytest.raises(RuntimeError) as exc_info:
        command.backfill_planning_categories(
            session,
            classifier=Mock(return_value="residential"),
            output=StringIO(),
        )

    assert exc_info.value is failure
    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()


def test_rerun_skips_already_categorised_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    applications = [
        _application(1, category="commercial"),
        _application(2),
        _application(3),
    ]

    def load_null_batch(
        _session: Session,
        batch_size: int,
        after_id: int | None,
    ) -> list[PlanningApplication]:
        return [
            application
            for application in sorted(applications, key=lambda item: item.id)
            if application.category is None
            and (after_id is None or application.id > after_id)
        ][:batch_size]

    monkeypatch.setattr(command, "load_uncategorised_batch", load_null_batch)
    monkeypatch.setattr(
        command,
        "has_uncategorised_records",
        lambda _session: any(
            application.category is None for application in applications
        ),
    )
    classifier = Mock(side_effect=["residential", "energy"])

    first_run = command.backfill_planning_categories(
        session,
        batch_size=1,
        max_batches=1,
        classifier=classifier,
        output=StringIO(),
    )
    second_run = command.backfill_planning_categories(
        session,
        batch_size=1,
        classifier=classifier,
        output=StringIO(),
    )

    assert first_run.records_categorised == 1
    assert first_run.uncategorised_records_remain is True
    assert second_run.records_categorised == 1
    assert second_run.uncategorised_records_remain is False
    assert [application.category for application in applications] == [
        "commercial",
        "residential",
        "energy",
    ]
    assert classifier.call_count == 2
    assert session.commit.call_count == 2


def test_empty_database_does_not_classify_or_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    classifier = Mock()
    monkeypatch.setattr(
        command,
        "load_uncategorised_batch",
        Mock(return_value=[]),
    )

    result = command.backfill_planning_categories(
        session,
        classifier=classifier,
        output=StringIO(),
    )

    assert result.batches_completed == 0
    assert result.records_categorised == 0
    assert result.category_counts == _category_counts()
    assert result.uncategorised_records_remain is False
    classifier.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--batch-size", "0"),
        ("--batch-size", "-1"),
        ("--batch-size", "true"),
        ("--batch-size", "1.5"),
        ("--max-batches", "0"),
        ("--max-batches", "-1"),
        ("--max-batches", "false"),
        ("--max-batches", "1.5"),
    ],
)
def test_parser_rejects_invalid_cli_arguments(option: str, value: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        command.build_parser().parse_args([option, value])

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("batch_size", "max_batches"),
    [(0, None), (-1, None), (True, None), (1000, 0), (1000, -1), (1000, True)],
)
def test_runner_rejects_invalid_programmatic_options(
    batch_size: int,
    max_batches: int | None,
) -> None:
    with pytest.raises(ValueError):
        command.backfill_planning_categories(
            Mock(spec=Session),
            batch_size=batch_size,
            max_batches=max_batches,
            output=StringIO(),
        )


def test_main_uses_defaults_closes_session_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    result = command.BackfillResult(
        batches_completed=0,
        records_categorised=0,
        category_counts=_category_counts(),
        uncategorised_records_remain=False,
    )
    backfill = Mock(return_value=result)
    monkeypatch.setattr(command, "backfill_planning_categories", backfill)
    classifier = Mock()
    stdout = StringIO()
    stderr = StringIO()

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        classifier=classifier,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    backfill.assert_called_once_with(
        session,
        batch_size=1000,
        max_batches=None,
        classifier=classifier,
        output=stdout,
    )
    session.close.assert_called_once_with()
    assert "batches completed=0" in stdout.getvalue()
    assert "records categorised=0" in stdout.getvalue()
    assert "uncategorised records remain=no" in stdout.getvalue()
    assert "residential=0" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_main_passes_custom_batch_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    result = command.BackfillResult(
        batches_completed=2,
        records_categorised=50,
        category_counts=_category_counts(residential=50),
        uncategorised_records_remain=True,
    )
    backfill = Mock(return_value=result)
    monkeypatch.setattr(command, "backfill_planning_categories", backfill)

    exit_code = command.main(
        ["--batch-size", "25", "--max-batches", "2"],
        session_factory=Mock(return_value=session),
        classifier=Mock(),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert backfill.call_args.kwargs["batch_size"] == 25
    assert backfill.call_args.kwargs["max_batches"] == 2
    session.close.assert_called_once_with()


def test_main_failure_rolls_back_closes_session_and_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    failure = RuntimeError("database unavailable")
    monkeypatch.setattr(
        command,
        "load_uncategorised_batch",
        Mock(side_effect=failure),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        classifier=Mock(),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "Planning category backfill failed: database unavailable\n"
    )
