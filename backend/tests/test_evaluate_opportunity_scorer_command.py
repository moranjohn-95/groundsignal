from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock, call

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from backend.app.commands import evaluate_opportunity_scorer as command
from backend.app.services.opportunity_scorer import (
    SCORE_COMPONENT_MAXIMUMS,
    ElectricalEvidenceLevel,
    ElectricalWorkBrief,
    OpportunityScoreBreakdown,
    OpportunityScoreComponent,
    OpportunityScoreResult,
    opportunity_level_for_score,
)


EVALUATION_DATE = date(2026, 8, 23)


def _record(
    identifier: int,
    *,
    application_number: str | None = None,
    planning_authority: str = "Kerry County Council",
    description: str | None = "Construction of a commercial building.",
    application_type: str | None = "Permission",
    number_residential_units: int | None = None,
    floor_area: float | None = 500.0,
    received_date: date | None = EVALUATION_DATE,
    category: str = "commercial",
) -> command.SampledOpportunityApplication:
    return command.SampledOpportunityApplication(
        id=identifier,
        application_number=application_number or f"APP-{identifier}",
        planning_authority=planning_authority,
        description=description,
        application_type=application_type,
        number_residential_units=number_residential_units,
        floor_area=floor_area,
        received_date=received_date,
        category=category,
    )


def _score_result(
    score: int,
    *,
    raw_score: int | None = None,
    evidence_level: ElectricalEvidenceLevel = "direct",
    score_breakdown: OpportunityScoreBreakdown | None = None,
) -> OpportunityScoreResult:
    raw_score = score if raw_score is None else raw_score
    if score_breakdown is None:
        remaining = raw_score
        components = []
        for maximum in (30, 30, 20, 10, 10):
            component = min(remaining, maximum)
            components.append(component)
            remaining -= component
        score_breakdown = OpportunityScoreBreakdown(*components)

    component_values = (
        score_breakdown.project_scope,
        score_breakdown.electrical_relevance,
        score_breakdown.project_scale,
        score_breakdown.lead_timing,
        score_breakdown.category_fit,
    )
    return OpportunityScoreResult(
        opportunity_score=score,
        raw_opportunity_score=raw_score,
        opportunity_level=opportunity_level_for_score(score),
        score_breakdown=score_breakdown,
        score_components=tuple(
            OpportunityScoreComponent(
                name=name,
                points_awarded=points,
                maximum_points=SCORE_COMPONENT_MAXIMUMS[name],
                explanation="Test scoring evidence.",
            )
            for name, points in zip(SCORE_COMPONENT_MAXIMUMS, component_values)
        ),
        reasons=("Test evidence",),
        electrical_work_brief=ElectricalWorkBrief(
            evidence_level=evidence_level,
            summary="Electrical work is not evidenced by the available planning data.",
            signals=(),
        ),
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
    monkeypatch.setattr(command, "load_recent_sample", loader)

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        evaluation_date=EVALUATION_DATE,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    loader.assert_called_once_with(session, 200)
    session.close.assert_called_once_with()


def test_command_accepts_custom_sample_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    loader = Mock(return_value=[])
    monkeypatch.setattr(command, "load_recent_sample", loader)

    exit_code = command.main(
        ["--sample-size", "750"],
        session_factory=Mock(return_value=session),
        evaluation_date=EVALUATION_DATE,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    loader.assert_called_once_with(session, 750)


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


def test_sample_statement_is_recent_deterministic_and_bounded() -> None:
    first = command.build_sample_statement(200).compile(
        dialect=postgresql.dialect()
    )
    second = command.build_sample_statement(200).compile(
        dialect=postgresql.dialect()
    )
    sql = str(first)

    assert sql == str(second)
    assert "category IS NOT NULL" in sql
    assert "received_date DESC NULLS LAST" in sql
    assert "id DESC" in sql
    assert "LIMIT" in sql
    assert 200 in first.params.values()


def test_sample_statement_selects_only_scorer_and_report_fields() -> None:
    compiled = command.build_sample_statement(10).compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled)

    for column_name in (
        "id",
        "application_number",
        "planning_authority",
        "description",
        "application_type",
        "number_residential_units",
        "floor_area",
        "received_date",
        "category",
    ):
        assert column_name in sql
    for excluded_column in (
        "location",
        "address",
        "created_at",
        "updated_at",
    ):
        assert excluded_column not in sql
    assert sql.lstrip().startswith("SELECT")
    assert "UPDATE" not in sql
    assert "INSERT" not in sql
    assert "DELETE" not in sql


def test_scorer_receives_exact_real_record_values() -> None:
    record = _record(
        42,
        application_number="26/0042",
        description="Construction of a solar installation.",
        application_type="Permission Consequent",
        number_residential_units=3,
        floor_area=975.5,
        received_date=date(2026, 8, 10),
        category="energy",
    )
    scorer = Mock(return_value=_score_result(75))

    evaluation = command.evaluate_sample(
        [record],
        evaluation_date=EVALUATION_DATE,
        scorer=scorer,
    )

    scorer.assert_called_once_with(
        description="Construction of a solar installation.",
        application_type="Permission Consequent",
        number_residential_units=3,
        floor_area=975.5,
        received_date=date(2026, 8, 10),
        category="energy",
        current_date=EVALUATION_DATE,
    )
    assert evaluation.total_evaluated == 1


def test_results_are_sorted_by_score_then_recency_then_id() -> None:
    records = [
        _record(3, received_date=EVALUATION_DATE - timedelta(days=2)),
        _record(2, received_date=EVALUATION_DATE),
        _record(1, received_date=EVALUATION_DATE),
        _record(4, received_date=EVALUATION_DATE),
    ]
    scorer = Mock(
        side_effect=[
            _score_result(90),
            _score_result(70),
            _score_result(70),
            _score_result(40),
        ]
    )

    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=scorer,
    )

    assert [result.application.id for result in evaluation.results] == [3, 1, 2, 4]


def test_distribution_and_summary_statistics_are_calculated() -> None:
    records = [_record(identifier) for identifier in range(1, 7)]
    scorer = Mock(
        side_effect=[
            _score_result(90),
            _score_result(80),
            _score_result(65),
            _score_result(45),
            _score_result(25),
            _score_result(10),
        ]
    )

    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=scorer,
    )

    assert evaluation.level_counts == {
        "very_high": 2,
        "high": 1,
        "medium": 1,
        "low": 1,
        "very_low": 1,
    }
    assert evaluation.average_score == pytest.approx(52.5)
    assert evaluation.minimum_score == 10
    assert evaluation.maximum_score == 90


def test_electrical_evidence_and_cap_metrics_are_calculated() -> None:
    records = [_record(identifier) for identifier in range(1, 5)]
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(
            side_effect=[
                _score_result(
                    39,
                    raw_score=70,
                    evidence_level="unavailable",
                    score_breakdown=OpportunityScoreBreakdown(30, 0, 20, 10, 10),
                ),
                _score_result(
                    56,
                    raw_score=56,
                    evidence_level="possible",
                    score_breakdown=OpportunityScoreBreakdown(20, 6, 10, 10, 10),
                ),
                _score_result(
                    79,
                    raw_score=85,
                    evidence_level="inferred",
                    score_breakdown=OpportunityScoreBreakdown(30, 15, 20, 10, 10),
                ),
                _score_result(
                    28,
                    raw_score=28,
                    evidence_level="direct",
                    score_breakdown=OpportunityScoreBreakdown(5, 20, 0, 0, 3),
                ),
            ]
        ),
    )

    assert evaluation.evidence_counts == {
        "unavailable": 1,
        "possible": 1,
        "inferred": 1,
        "direct": 1,
    }
    assert evaluation.electrical_relevance_counts == {0: 1, 6: 1, 15: 1, 20: 1}
    assert evaluation.capped_application_count == 2
    assert evaluation.average_raw_score == pytest.approx(59.75)
    assert evaluation.average_effective_score == pytest.approx(50.5)
    assert evaluation.average_cap_reduction == pytest.approx(18.5)
    assert evaluation.maximum_cap_reduction == 31
    assert [
        result.application.application_number
        for result in evaluation.suspicious_examples[
            "unavailable with raw score >= 40"
        ]
    ] == ["APP-1"]
    assert [
        result.application.application_number
        for result in evaluation.suspicious_examples[
            "unavailable with meaningful building scope"
        ]
    ] == ["APP-1"]
    assert evaluation.suspicious_examples["possible with very high raw score"] == ()
    assert [
        result.application.application_number
        for result in evaluation.suspicious_examples[
            "inferred with raw score >= 80"
        ]
    ] == ["APP-3"]
    assert [
        result.application.application_number
        for result in evaluation.suspicious_examples[
            "direct evidence with unexpectedly low effective score"
        ]
    ] == ["APP-4"]
    assert (
        evaluation.suspicious_examples[
            "high/very-high effective opportunity with weak electrical evidence"
        ]
        == ()
    )
    assert evaluation.consistency_violations == ()


def test_report_prints_evidence_cap_and_suspicious_combination_sections() -> None:
    records = [_record(identifier) for identifier in range(1, 5)]
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(
            side_effect=[
                _score_result(
                    39,
                    raw_score=70,
                    evidence_level="unavailable",
                    score_breakdown=OpportunityScoreBreakdown(30, 0, 20, 10, 10),
                ),
                _score_result(
                    56,
                    raw_score=56,
                    evidence_level="possible",
                    score_breakdown=OpportunityScoreBreakdown(20, 6, 10, 10, 10),
                ),
                _score_result(
                    79,
                    raw_score=85,
                    evidence_level="inferred",
                    score_breakdown=OpportunityScoreBreakdown(30, 15, 20, 10, 10),
                ),
                _score_result(
                    28,
                    raw_score=28,
                    evidence_level="direct",
                    score_breakdown=OpportunityScoreBreakdown(5, 20, 0, 0, 3),
                ),
            ]
        ),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    report = output.getvalue()
    assert "Electrical evidence distribution:" in report
    assert "unavailable / 0: 1 (25.0%)" in report
    assert "possible / 1: 1 (25.0%)" in report
    assert "inferred / 2: 1 (25.0%)" in report
    assert "direct / 3: 1 (25.0%)" in report
    assert "Electrical relevance point distribution:" in report
    assert "  15: 1" in report
    assert "Raw vs effective scores:" in report
    assert "applications capped: 2" in report
    assert "average raw score: 59.8" in report
    assert "average effective score: 50.5" in report
    assert "average cap reduction: 18.5" in report
    assert "maximum cap reduction: 31" in report
    assert "Suspicious combinations:" in report
    assert "unavailable with meaningful building scope:" in report
    assert "Representative examples by electrical evidence:" in report
    assert "application_number=APP-1" in report
    assert "evidence=unavailable/0" in report
    assert "electrical_relevance=0" in report
    assert "raw_score=70" in report
    assert "effective_score=39" in report
    assert "Consistency checks:" in report
    assert "all structural checks passed" in report


def test_evidence_examples_are_limited_to_ten_per_level() -> None:
    records = [_record(identifier) for identifier in range(1, 13)]
    score = _score_result(
        39,
        raw_score=70,
        evidence_level="unavailable",
        score_breakdown=OpportunityScoreBreakdown(30, 0, 20, 10, 10),
    )
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(side_effect=[score] * len(records)),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    evidence_examples = output.getvalue().split(
        "Representative examples by electrical evidence:"
    )[1]
    unavailable_examples = evidence_examples.split("  possible / 1:")[0]
    assert unavailable_examples.count("  id=") == 10


@pytest.mark.parametrize(
    ("score", "expected_message"),
    [
        (
            _score_result(
                40,
                raw_score=40,
                evidence_level="unavailable",
                score_breakdown=OpportunityScoreBreakdown(20, 0, 10, 5, 5),
            ),
            "unavailable evidence has effective score 40, above its maximum of 39",
        ),
        (
            _score_result(
                60,
                raw_score=60,
                evidence_level="possible",
                score_breakdown=OpportunityScoreBreakdown(30, 6, 12, 2, 10),
            ),
            "possible evidence has effective score 60, above its maximum of 59",
        ),
        (
            _score_result(
                80,
                raw_score=80,
                evidence_level="inferred",
                score_breakdown=OpportunityScoreBreakdown(30, 12, 20, 8, 10),
            ),
            "inferred evidence has effective score 80, above its maximum of 79",
        ),
        (
            _score_result(
                70,
                raw_score=80,
                evidence_level="direct",
                score_breakdown=OpportunityScoreBreakdown(30, 20, 20, 10, 0),
            ),
            "direct evidence has raw score 80 but effective score 70",
        ),
        (
            _score_result(
                39,
                raw_score=70,
                evidence_level="unavailable",
                score_breakdown=OpportunityScoreBreakdown(30, 0, 20, 10, 9),
            ),
            "score breakdown total 69 does not match raw score 70",
        ),
    ],
)
def test_structural_consistency_violations_are_flagged(
    score: OpportunityScoreResult,
    expected_message: str,
) -> None:
    evaluation = command.evaluate_sample(
        [_record(1)],
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(return_value=score),
    )

    assert len(evaluation.consistency_violations) == 1
    assert expected_message in evaluation.consistency_violations[0]


def test_suspicious_examples_do_not_cause_main_to_fail() -> None:
    session = _session_with_rows(
        [
            {
                "id": 1,
                "application_number": "26/1",
                "planning_authority": "Kerry County Council",
                "description": "Construction of a large building.",
                "application_type": "Permission",
                "number_residential_units": None,
                "floor_area": 5000.0,
                "received_date": EVALUATION_DATE,
                "category": "other",
            }
        ]
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        scorer=Mock(
            return_value=_score_result(
                39,
                raw_score=70,
                evidence_level="unavailable",
                score_breakdown=OpportunityScoreBreakdown(30, 0, 20, 10, 10),
            )
        ),
        evaluation_date=EVALUATION_DATE,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert "unavailable with raw score >= 40:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_structural_consistency_violations_make_main_return_non_zero() -> None:
    session = _session_with_rows(
        [
            {
                "id": 1,
                "application_number": "26/1",
                "planning_authority": "Kerry County Council",
                "description": "Construction of a building.",
                "application_type": "Permission",
                "number_residential_units": None,
                "floor_area": None,
                "received_date": EVALUATION_DATE,
                "category": "other",
            }
        ]
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        scorer=Mock(
            return_value=_score_result(
                40,
                raw_score=40,
                evidence_level="unavailable",
                score_breakdown=OpportunityScoreBreakdown(20, 0, 10, 5, 5),
            )
        ),
        evaluation_date=EVALUATION_DATE,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert "WARNING: application 26/1" in stdout.getvalue()
    assert "structural consistency violations" in stderr.getvalue()


def test_report_prints_distribution_percentages_and_statistics() -> None:
    records = [_record(identifier) for identifier in range(1, 5)]
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(
            side_effect=[
                _score_result(90),
                _score_result(70),
                _score_result(50),
                _score_result(10),
            ]
        ),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    report = output.getvalue()
    assert "Total evaluated: 4" in report
    assert "very_high: 1 (25.0%)" in report
    assert "low: 0 (0.0%)" in report
    assert "average: 55.0" in report
    assert "minimum: 10" in report
    assert "maximum: 90" in report


def test_report_prints_required_record_fields_and_short_description() -> None:
    record = _record(
        42,
        application_number="26/0042",
        planning_authority="Cork City Council",
        description="First line\n" + ("long description " * 20),
        category="industrial",
    )
    evaluation = command.evaluate_sample(
        [record],
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(return_value=_score_result(75)),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    report = output.getvalue()
    assert "id=42" in report
    assert "application_number=26/0042" in report
    assert "authority=Cork City Council" in report
    assert "category=industrial" in report
    assert "evidence=direct/3" in report
    assert "electrical_relevance=30" in report
    assert "raw_score=75" in report
    assert "effective_score=75" in report
    assert "level=high" in report
    assert "First line long description" in report
    assert "\nlong description" not in report
    assert "..." in report


def test_report_limits_highest_scoring_section_to_top_thirty() -> None:
    records = [_record(identifier) for identifier in range(1, 36)]
    scores = [_score_result(score) for score in range(35, 0, -1)]
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(side_effect=scores),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    top_section = output.getvalue().split(
        f"Top {command.TOP_RESULT_COUNT} opportunities:"
    )[1].split("Representative examples by opportunity level:")[0]
    assert top_section.count("  id=") == 30


def test_report_includes_representative_examples_for_every_level() -> None:
    records = [_record(identifier) for identifier in range(1, 6)]
    evaluation = command.evaluate_sample(
        records,
        evaluation_date=EVALUATION_DATE,
        scorer=Mock(
            side_effect=[
                _score_result(90),
                _score_result(70),
                _score_result(50),
                _score_result(30),
                _score_result(10),
            ]
        ),
    )
    output = StringIO()

    command.print_evaluation(evaluation, output)

    examples = output.getvalue().split(
        "Representative examples by opportunity level:"
    )[1].split("Representative examples by electrical evidence:")[0]
    for level in command.OPPORTUNITY_LEVELS:
        assert f"  {level}:" in examples
    assert examples.count("  id=") == 5


def test_description_placeholder_and_truncation() -> None:
    assert command._shorten_description(None) == "(no description)"
    assert command._shorten_description(" \r\n ") == "(no description)"

    shortened = command._shorten_description("description " * 30)

    assert len(shortened) <= command.DESCRIPTION_MAX_LENGTH
    assert shortened.endswith("...")


def test_run_is_read_only_and_always_closes_session() -> None:
    rows = [
        {
            "id": 1,
            "application_number": "26/1",
            "planning_authority": "Kerry County Council",
            "description": "Construction of a commercial building.",
            "application_type": "Permission",
            "number_residential_units": None,
            "floor_area": 800.0,
            "received_date": EVALUATION_DATE,
            "category": "commercial",
        }
    ]
    session = _session_with_rows(rows)

    evaluation = command.run_evaluation(
        sample_size=200,
        session_factory=Mock(return_value=session),
        scorer=Mock(return_value=_score_result(70)),
        evaluation_date=EVALUATION_DATE,
        output=StringIO(),
    )

    assert evaluation.total_evaluated == 1
    session.execute.assert_called_once()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.close.assert_called_once_with()


def test_session_closes_and_main_returns_failure_when_scoring_fails() -> None:
    rows = [
        {
            "id": 1,
            "application_number": "26/1",
            "planning_authority": "Kerry County Council",
            "description": "Test development.",
            "application_type": "Permission",
            "number_residential_units": None,
            "floor_area": None,
            "received_date": EVALUATION_DATE,
            "category": "other",
        }
    ]
    session = _session_with_rows(rows)
    stderr = StringIO()

    exit_code = command.main(
        [],
        session_factory=Mock(return_value=session),
        scorer=Mock(side_effect=RuntimeError("scorer failed")),
        evaluation_date=EVALUATION_DATE,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == 1
    assert "Opportunity scorer evaluation failed: scorer failed" in stderr.getvalue()
    session.close.assert_called_once_with()
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_empty_result_has_zero_distribution_and_clear_output() -> None:
    session = _session_with_rows([])
    scorer = Mock()
    output = StringIO()

    evaluation = command.run_evaluation(
        sample_size=200,
        session_factory=Mock(return_value=session),
        scorer=scorer,
        evaluation_date=EVALUATION_DATE,
        output=output,
    )

    assert evaluation.total_evaluated == 0
    assert evaluation.average_score == 0.0
    assert evaluation.minimum_score is None
    assert evaluation.maximum_score is None
    assert all(count == 0 for count in evaluation.level_counts.values())
    assert "minimum: n/a" in output.getvalue()
    assert "maximum: n/a" in output.getvalue()
    assert "(none)" in output.getvalue()
    scorer.assert_not_called()
    session.close.assert_called_once_with()
