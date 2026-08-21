from io import StringIO
from unittest.mock import Mock, call

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.commands import evaluate_planning_classifier as command


def _record(
    identifier: int,
    description: str | None = "Construction of a dwelling.",
    *,
    application_number: str | None = None,
    application_type: str | None = "Permission",
    number_residential_units: int | None = 1,
    floor_area: float | None = 120.0,
) -> command.SampledPlanningApplication:
    return command.SampledPlanningApplication(
        id=identifier,
        application_number=application_number or f"APP-{identifier}",
        description=description,
        application_type=application_type,
        number_residential_units=number_residential_units,
        floor_area=floor_area,
    )


def _session_with_rows(rows: list[dict]) -> Mock:
    session = Mock(spec=Session)
    result = Mock()
    result.mappings.return_value.all.return_value = rows
    session.execute.return_value = result
    return session


def test_command_uses_default_sample_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    loader = Mock(return_value=[])
    monkeypatch.setattr(command, "load_deterministic_sample", loader)

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    loader.assert_called_once_with(session, 500)
    session.close.assert_called_once_with()


def test_command_passes_custom_sample_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    loader = Mock(return_value=[])
    monkeypatch.setattr(command, "load_deterministic_sample", loader)

    exit_code = command.main(
        ["--sample-size", "1250"],
        session_factory=Mock(return_value=session),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    loader.assert_called_once_with(session, 1250)
    session.close.assert_called_once_with()


@pytest.mark.parametrize("sample_size", ["0", "-1", "5001", "true", "1.5"])
def test_command_rejects_invalid_sample_sizes(sample_size: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        command.build_parser().parse_args(["--sample-size", sample_size])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("sample_size", [1, 5000])
def test_command_accepts_sample_size_boundaries(sample_size: int) -> None:
    args = command.build_parser().parse_args(
        ["--sample-size", str(sample_size)]
    )

    assert args.sample_size == sample_size


def test_sample_statement_is_deterministic_and_evenly_bucketed() -> None:
    dialect = postgresql.dialect()
    first = command.build_sample_statement(500).compile(dialect=dialect)
    second = command.build_sample_statement(500).compile(dialect=dialect)
    sql = str(first)

    assert sql == str(second)
    assert "ntile" in sql
    assert "OVER (ORDER BY planning_applications.id ASC)" in sql
    assert "DISTINCT ON" in sql
    assert "ORDER BY" in sql
    assert "sample_bucket ASC" in sql
    assert "id ASC" in sql
    assert 500 in first.params.values()


def test_sample_statement_selects_only_evaluation_fields() -> None:
    compiled = command.build_sample_statement(10).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    for column_name in (
        "id",
        "application_number",
        "description",
        "application_type",
        "number_residential_units",
        "floor_area",
    ):
        assert column_name in sql
    for excluded_column in ("location", "created_at", "updated_at"):
        assert excluded_column not in sql
    assert sql.lstrip().startswith("SELECT")
    assert "UPDATE" not in sql
    assert "INSERT" not in sql
    assert "DELETE" not in sql


def test_classifier_is_called_with_each_records_classification_fields() -> None:
    records = [
        _record(1),
        _record(
            2,
            "Construction of a solar farm.",
            application_type="Permission Consequent",
            number_residential_units=0,
            floor_area=900.0,
        ),
    ]
    classifier = Mock(side_effect=["residential", "energy"])

    evaluation = command.evaluate_sample(records, classifier)

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
            floor_area=900.0,
        ),
    ]
    assert evaluation.total_evaluated == 2


def test_evaluation_counts_every_category() -> None:
    records = [_record(identifier) for identifier in range(1, 8)]
    classifier = Mock(
        side_effect=[
            "residential",
            "commercial",
            "industrial",
            "energy",
            "infrastructure",
            "mixed_use",
            "other",
        ]
    )

    evaluation = command.evaluate_sample(records, classifier)

    assert evaluation.total_evaluated == 7
    assert evaluation.category_counts == {
        "residential": 1,
        "commercial": 1,
        "industrial": 1,
        "energy": 1,
        "infrastructure": 1,
        "mixed_use": 1,
        "other": 1,
    }


def test_report_prints_category_percentages() -> None:
    records = [_record(identifier) for identifier in range(1, 5)]
    classifier = Mock(
        side_effect=["residential", "residential", "residential", "other"]
    )
    evaluation = command.evaluate_sample(records, classifier)
    output = StringIO()

    command.print_evaluation(evaluation, output)

    report = output.getvalue()
    assert "Total evaluated: 4" in report
    assert "residential: 3 (75.0%)" in report
    assert "other: 1 (25.0%)" in report
    assert "commercial: 0 (0.0%)" in report


def test_report_prints_representative_record_fields() -> None:
    record = _record(
        42,
        "Construction of a retail shop.",
        application_number="24/0042",
    )
    evaluation = command.evaluate_sample([record], Mock(return_value="commercial"))
    output = StringIO()

    command.print_evaluation(evaluation, output)

    report = output.getvalue()
    assert "id=42" in report
    assert "application_number=24/0042" in report
    assert "category=commercial" in report
    assert "description=Construction of a retail shop." in report


def test_evaluation_keeps_at_most_five_examples_per_category() -> None:
    records = [_record(identifier) for identifier in range(1, 8)]

    evaluation = command.evaluate_sample(
        records,
        Mock(return_value="residential"),
    )

    examples = evaluation.representative_examples["residential"]
    assert [example.id for example in examples] == [1, 2, 3, 4, 5]
    assert evaluation.category_counts["residential"] == 7


def test_description_is_normalized_and_truncated_for_terminal_output() -> None:
    description = "  First line\n" + ("long description " * 20)

    shortened = command._shorten_description(description)

    assert "\n" not in shortened
    assert len(shortened) <= command.DESCRIPTION_MAX_LENGTH
    assert shortened.endswith("...")


def test_empty_description_has_clear_placeholder() -> None:
    assert command._shorten_description(None) == "(no description)"
    assert command._shorten_description(" \r\n ") == "(no description)"


def test_run_is_read_only_and_always_closes_session() -> None:
    rows = [
        {
            "id": 1,
            "application_number": "24/1",
            "description": "Construction of a dwelling.",
            "application_type": "Permission",
            "number_residential_units": 1,
            "floor_area": 120.0,
        }
    ]
    session = _session_with_rows(rows)

    evaluation = command.run_evaluation(
        sample_size=500,
        session_factory=Mock(return_value=session),
        classifier=Mock(return_value="residential"),
        output=StringIO(),
    )

    assert evaluation.total_evaluated == 1
    session.execute.assert_called_once()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.close.assert_called_once_with()


def test_session_closes_when_classification_fails() -> None:
    rows = [
        {
            "id": 1,
            "application_number": "24/1",
            "description": "Test development.",
            "application_type": "Permission",
            "number_residential_units": None,
            "floor_area": None,
        }
    ]
    session = _session_with_rows(rows)
    failure = RuntimeError("classifier failed")

    with pytest.raises(RuntimeError) as exc_info:
        command.run_evaluation(
            sample_size=500,
            session_factory=Mock(return_value=session),
            classifier=Mock(side_effect=failure),
            output=StringIO(),
        )

    assert exc_info.value is failure
    session.close.assert_called_once_with()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_empty_database_result_prints_zero_distribution() -> None:
    session = _session_with_rows([])
    classifier = Mock()
    output = StringIO()

    evaluation = command.run_evaluation(
        sample_size=500,
        session_factory=Mock(return_value=session),
        classifier=classifier,
        output=output,
    )

    assert evaluation.total_evaluated == 0
    assert all(count == 0 for count in evaluation.category_counts.values())
    assert "Total evaluated: 0" in output.getvalue()
    assert "residential: 0 (0.0%)" in output.getvalue()
    assert "(none)" in output.getvalue()
    classifier.assert_not_called()
    session.close.assert_called_once_with()
