import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
import sys
from typing import TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ..database import SessionLocal
from ..models import PlanningApplication
from ..services.opportunity_scorer import (
    ELECTRICAL_EVIDENCE_SCORE_CEILINGS,
    ElectricalEvidenceLevel,
    OpportunityLevel,
    OpportunityScoreResult,
    score_planning_application_opportunity,
)
from ..services.planning_classifier import PlanningApplicationCategory


DEFAULT_SAMPLE_SIZE = 200
MIN_SAMPLE_SIZE = 1
MAX_SAMPLE_SIZE = 5000
TOP_RESULT_COUNT = 30
MAX_EXAMPLES_PER_LEVEL = 5
MAX_EXAMPLES_PER_EVIDENCE_LEVEL = 10
MAX_SUSPICIOUS_EXAMPLES = 10
DESCRIPTION_MAX_LENGTH = 110
MEANINGFUL_BUILDING_SCOPE_MINIMUM = 20
VERY_HIGH_RAW_SCORE_MINIMUM = 80
DIRECT_LOW_TOTAL_SCORE_MAXIMUM = 39
HIGH_EFFECTIVE_SCORE_MINIMUM = 60

OPPORTUNITY_LEVELS: tuple[OpportunityLevel, ...] = (
    "very_high",
    "high",
    "medium",
    "low",
    "very_low",
)

ELECTRICAL_EVIDENCE_LEVELS: tuple[ElectricalEvidenceLevel, ...] = (
    "unavailable",
    "possible",
    "inferred",
    "direct",
)

ELECTRICAL_EVIDENCE_VALUES: dict[ElectricalEvidenceLevel, int] = {
    "unavailable": 0,
    "possible": 1,
    "inferred": 2,
    "direct": 3,
}

SUSPICIOUS_COMBINATION_LABELS = (
    "unavailable with raw score >= 40",
    "unavailable with meaningful building scope",
    "possible with very high raw score",
    "inferred with raw score >= 80",
    "direct evidence with unexpectedly low effective score",
    "high/very-high effective opportunity with weak electrical evidence",
)

SessionFactory = Callable[[], Session]
OpportunityScorer = Callable[..., OpportunityScoreResult]


@dataclass(frozen=True)
class SampledOpportunityApplication:
    id: int
    application_number: str
    planning_authority: str
    description: str | None
    application_type: str | None
    number_residential_units: int | None
    floor_area: float | None
    received_date: date | None
    category: PlanningApplicationCategory


@dataclass(frozen=True)
class ScoredOpportunityApplication:
    application: SampledOpportunityApplication
    score: OpportunityScoreResult


@dataclass(frozen=True)
class OpportunityScorerEvaluation:
    evaluated_on: date
    results: tuple[ScoredOpportunityApplication, ...]
    level_counts: dict[OpportunityLevel, int]
    average_score: float
    minimum_score: int | None
    maximum_score: int | None
    evidence_counts: dict[ElectricalEvidenceLevel, int]
    electrical_relevance_counts: dict[int, int]
    capped_application_count: int
    average_raw_score: float
    average_effective_score: float
    average_cap_reduction: float | None
    maximum_cap_reduction: int | None
    suspicious_examples: dict[str, tuple[ScoredOpportunityApplication, ...]]
    consistency_violations: tuple[str, ...]

    @property
    def total_evaluated(self) -> int:
        return len(self.results)


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _validate_sample_size(sample_size: int) -> int:
    if (
        isinstance(sample_size, bool)
        or not isinstance(sample_size, int)
        or not MIN_SAMPLE_SIZE <= sample_size <= MAX_SAMPLE_SIZE
    ):
        raise ValueError(
            f"sample_size must be an integer between "
            f"{MIN_SAMPLE_SIZE} and {MAX_SAMPLE_SIZE}"
        )
    return sample_size


def _sample_size_argument(value: str) -> int:
    try:
        sample_size = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sample size must be an integer") from exc

    try:
        return _validate_sample_size(sample_size)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the V1 electrician opportunity scorer against recent "
            "planning applications."
        )
    )
    parser.add_argument(
        "--sample-size",
        type=_sample_size_argument,
        default=DEFAULT_SAMPLE_SIZE,
        help=(
            f"number of recent records to evaluate "
            f"(default: {DEFAULT_SAMPLE_SIZE}; "
            f"range: {MIN_SAMPLE_SIZE}-{MAX_SAMPLE_SIZE})"
        ),
    )
    return parser


def build_sample_statement(sample_size: int) -> Select:
    """Select a deterministic recent sample using only scorer/report fields."""
    sample_size = _validate_sample_size(sample_size)
    return (
        select(
            PlanningApplication.id,
            PlanningApplication.application_number,
            PlanningApplication.planning_authority,
            PlanningApplication.description,
            PlanningApplication.application_type,
            PlanningApplication.number_residential_units,
            PlanningApplication.floor_area,
            PlanningApplication.received_date,
            PlanningApplication.category,
        )
        .where(PlanningApplication.category.is_not(None))
        .order_by(
            PlanningApplication.received_date.desc().nulls_last(),
            PlanningApplication.id.desc(),
        )
        .limit(sample_size)
    )


def load_recent_sample(
    session: Session,
    sample_size: int,
) -> list[SampledOpportunityApplication]:
    rows = session.execute(build_sample_statement(sample_size)).mappings().all()
    return [SampledOpportunityApplication(**row) for row in rows]


def evaluate_sample(
    records: Sequence[SampledOpportunityApplication],
    *,
    evaluation_date: date,
    scorer: OpportunityScorer = score_planning_application_opportunity,
) -> OpportunityScorerEvaluation:
    scored_records = []
    for record in records:
        score = scorer(
            description=record.description,
            application_type=record.application_type,
            number_residential_units=record.number_residential_units,
            floor_area=record.floor_area,
            received_date=record.received_date,
            category=record.category,
            current_date=evaluation_date,
        )
        scored_records.append(
            ScoredOpportunityApplication(application=record, score=score)
        )

    scored_records.sort(
        key=lambda result: (
            -result.score.opportunity_score,
            -(
                result.application.received_date.toordinal()
                if result.application.received_date is not None
                else date.min.toordinal()
            ),
            result.application.id,
        )
    )

    level_counts = {level: 0 for level in OPPORTUNITY_LEVELS}
    for result in scored_records:
        level_counts[result.score.opportunity_level] += 1

    scores = [result.score.opportunity_score for result in scored_records]
    raw_scores = [result.score.raw_opportunity_score for result in scored_records]
    cap_reductions = [
        result.score.raw_opportunity_score - result.score.opportunity_score
        for result in scored_records
        if result.score.raw_opportunity_score > result.score.opportunity_score
    ]
    evidence_counts = {evidence_level: 0 for evidence_level in ELECTRICAL_EVIDENCE_LEVELS}
    electrical_relevance_counts: dict[int, int] = {}
    for result in scored_records:
        score = result.score
        evidence_counts[score.electrical_work_brief.evidence_level] += 1
        electrical_relevance = score.score_breakdown.electrical_relevance
        electrical_relevance_counts[electrical_relevance] = (
            electrical_relevance_counts.get(electrical_relevance, 0) + 1
        )

    return OpportunityScorerEvaluation(
        evaluated_on=evaluation_date,
        results=tuple(scored_records),
        level_counts=level_counts,
        average_score=sum(scores) / len(scores) if scores else 0.0,
        minimum_score=min(scores) if scores else None,
        maximum_score=max(scores) if scores else None,
        evidence_counts=evidence_counts,
        electrical_relevance_counts=electrical_relevance_counts,
        capped_application_count=len(cap_reductions),
        average_raw_score=sum(raw_scores) / len(raw_scores) if raw_scores else 0.0,
        average_effective_score=sum(scores) / len(scores) if scores else 0.0,
        average_cap_reduction=(
            sum(cap_reductions) / len(cap_reductions) if cap_reductions else None
        ),
        maximum_cap_reduction=max(cap_reductions) if cap_reductions else None,
        suspicious_examples=_collect_suspicious_examples(scored_records),
        consistency_violations=_collect_consistency_violations(scored_records),
    )


def _shorten_description(
    description: str | None,
    max_length: int = DESCRIPTION_MAX_LENGTH,
) -> str:
    text = " ".join((description or "").split())
    if not text:
        return "(no description)"
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _print_result(
    result: ScoredOpportunityApplication,
    output: TextIO,
) -> None:
    application = result.application
    score = result.score
    print(
        f"  id={application.id} | "
        f"application_number={application.application_number} | "
        f"authority={application.planning_authority} | "
        f"category={application.category} | "
        f"evidence={score.electrical_work_brief.evidence_level}/"
        f"{ELECTRICAL_EVIDENCE_VALUES[score.electrical_work_brief.evidence_level]} | "
        f"electrical_relevance={score.score_breakdown.electrical_relevance} | "
        f"raw_score={score.raw_opportunity_score} | "
        f"effective_score={score.opportunity_score} | "
        f"level={score.opportunity_level} | "
        f"description={_shorten_description(application.description)}",
        file=output,
    )


def _collect_suspicious_examples(
    results: Sequence[ScoredOpportunityApplication],
) -> dict[str, tuple[ScoredOpportunityApplication, ...]]:
    examples = {label: [] for label in SUSPICIOUS_COMBINATION_LABELS}
    for result in results:
        score = result.score
        evidence_level = score.electrical_work_brief.evidence_level
        raw_score = score.raw_opportunity_score
        effective_score = score.opportunity_score
        project_scope = score.score_breakdown.project_scope

        if evidence_level == "unavailable" and raw_score >= 40:
            examples["unavailable with raw score >= 40"].append(result)
        if (
            evidence_level == "unavailable"
            and project_scope >= MEANINGFUL_BUILDING_SCOPE_MINIMUM
        ):
            examples["unavailable with meaningful building scope"].append(result)
        if evidence_level == "possible" and raw_score >= VERY_HIGH_RAW_SCORE_MINIMUM:
            examples["possible with very high raw score"].append(result)
        if evidence_level == "inferred" and raw_score >= VERY_HIGH_RAW_SCORE_MINIMUM:
            examples["inferred with raw score >= 80"].append(result)
        if (
            evidence_level == "direct"
            and effective_score <= DIRECT_LOW_TOTAL_SCORE_MAXIMUM
        ):
            examples[
                "direct evidence with unexpectedly low effective score"
            ].append(result)
        if (
            effective_score >= HIGH_EFFECTIVE_SCORE_MINIMUM
            and evidence_level in {"unavailable", "possible"}
        ):
            examples[
                "high/very-high effective opportunity with weak electrical evidence"
            ].append(result)

    return {
        label: tuple(results[:MAX_SUSPICIOUS_EXAMPLES])
        for label, results in examples.items()
    }


def _collect_consistency_violations(
    results: Sequence[ScoredOpportunityApplication],
) -> tuple[str, ...]:
    violations = []
    for result in results:
        application_number = result.application.application_number
        score = result.score
        evidence_level = score.electrical_work_brief.evidence_level
        raw_score = score.raw_opportunity_score
        effective_score = score.opportunity_score

        if evidence_level == "direct":
            if effective_score != raw_score:
                violations.append(
                    f"application {application_number}: direct evidence has "
                    f"raw score {raw_score} but effective score {effective_score}."
                )
        elif effective_score > ELECTRICAL_EVIDENCE_SCORE_CEILINGS[evidence_level]:
            violations.append(
                f"application {application_number}: {evidence_level} evidence "
                f"has effective score {effective_score}, above its maximum of "
                f"{ELECTRICAL_EVIDENCE_SCORE_CEILINGS[evidence_level]}."
            )

        if score.score_breakdown.total != raw_score:
            violations.append(
                f"application {application_number}: score breakdown total "
                f"{score.score_breakdown.total} does not match raw score {raw_score}."
            )

    return tuple(violations)


def print_evaluation(
    evaluation: OpportunityScorerEvaluation,
    output: TextIO | None = None,
) -> None:
    output = sys.stdout if output is None else output
    print("Electrician opportunity scorer evaluation", file=output)
    print(f"Evaluation date (UTC): {evaluation.evaluated_on.isoformat()}", file=output)
    print(f"Total evaluated: {evaluation.total_evaluated}", file=output)
    print("", file=output)
    print("Score distribution:", file=output)

    for level in OPPORTUNITY_LEVELS:
        count = evaluation.level_counts[level]
        percentage = (
            count / evaluation.total_evaluated * 100
            if evaluation.total_evaluated
            else 0.0
        )
        print(f"  {level}: {count} ({percentage:.1f}%)", file=output)

    minimum = (
        str(evaluation.minimum_score)
        if evaluation.minimum_score is not None
        else "n/a"
    )
    maximum = (
        str(evaluation.maximum_score)
        if evaluation.maximum_score is not None
        else "n/a"
    )
    print(f"  average: {evaluation.average_score:.1f}", file=output)
    print(f"  minimum: {minimum}", file=output)
    print(f"  maximum: {maximum}", file=output)

    print("", file=output)
    print("Electrical evidence distribution:", file=output)
    for evidence_level in ELECTRICAL_EVIDENCE_LEVELS:
        count = evaluation.evidence_counts[evidence_level]
        percentage = (
            count / evaluation.total_evaluated * 100
            if evaluation.total_evaluated
            else 0.0
        )
        print(
            f"  {evidence_level} / {ELECTRICAL_EVIDENCE_VALUES[evidence_level]}: "
            f"{count} ({percentage:.1f}%)",
            file=output,
        )

    print("", file=output)
    print("Electrical relevance point distribution:", file=output)
    if not evaluation.electrical_relevance_counts:
        print("  (none)", file=output)
    for points, count in sorted(evaluation.electrical_relevance_counts.items()):
        print(f"  {points}: {count}", file=output)

    average_cap_reduction = (
        f"{evaluation.average_cap_reduction:.1f}"
        if evaluation.average_cap_reduction is not None
        else "n/a"
    )
    maximum_cap_reduction = (
        str(evaluation.maximum_cap_reduction)
        if evaluation.maximum_cap_reduction is not None
        else "n/a"
    )
    print("", file=output)
    print("Raw vs effective scores:", file=output)
    print(f"  applications capped: {evaluation.capped_application_count}", file=output)
    print(f"  average raw score: {evaluation.average_raw_score:.1f}", file=output)
    print(
        f"  average effective score: {evaluation.average_effective_score:.1f}",
        file=output,
    )
    print(f"  average cap reduction: {average_cap_reduction}", file=output)
    print(f"  maximum cap reduction: {maximum_cap_reduction}", file=output)

    print("", file=output)
    print("Suspicious combinations:", file=output)
    for label in SUSPICIOUS_COMBINATION_LABELS:
        print(f"  {label}:", file=output)
        examples = evaluation.suspicious_examples[label]
        if not examples:
            print("    (none)", file=output)
            continue
        for result in examples:
            _print_result(result, output)

    print("", file=output)
    print("Consistency checks:", file=output)
    if not evaluation.consistency_violations:
        print("  all structural checks passed", file=output)
    for violation in evaluation.consistency_violations:
        print(f"  WARNING: {violation}", file=output)

    print("", file=output)
    print(f"Top {TOP_RESULT_COUNT} opportunities:", file=output)
    top_results = evaluation.results[:TOP_RESULT_COUNT]
    if not top_results:
        print("  (none)", file=output)
    for result in top_results:
        _print_result(result, output)

    print("", file=output)
    print("Representative examples by opportunity level:", file=output)
    for level in OPPORTUNITY_LEVELS:
        print(f"  {level}:", file=output)
        examples = [
            result
            for result in evaluation.results
            if result.score.opportunity_level == level
        ][:MAX_EXAMPLES_PER_LEVEL]
        if not examples:
            print("    (none)", file=output)
            continue
        for result in examples:
            _print_result(result, output)

    print("", file=output)
    print("Representative examples by electrical evidence:", file=output)
    for evidence_level in ELECTRICAL_EVIDENCE_LEVELS:
        print(
            f"  {evidence_level} / {ELECTRICAL_EVIDENCE_VALUES[evidence_level]}:",
            file=output,
        )
        examples = [
            result
            for result in evaluation.results
            if result.score.electrical_work_brief.evidence_level == evidence_level
        ][:MAX_EXAMPLES_PER_EVIDENCE_LEVEL]
        if not examples:
            print("    (none)", file=output)
            continue
        for result in examples:
            _print_result(result, output)


def run_evaluation(
    *,
    sample_size: int,
    session_factory: SessionFactory | None = None,
    scorer: OpportunityScorer | None = None,
    evaluation_date: date | None = None,
    output: TextIO | None = None,
) -> OpportunityScorerEvaluation:
    session_factory = SessionLocal if session_factory is None else session_factory
    scorer = (
        score_planning_application_opportunity if scorer is None else scorer
    )
    evaluation_date = (
        _current_utc_date() if evaluation_date is None else evaluation_date
    )

    session = session_factory()
    try:
        records = load_recent_sample(session, sample_size)
        evaluation = evaluate_sample(
            records,
            evaluation_date=evaluation_date,
            scorer=scorer,
        )
    finally:
        session.close()

    print_evaluation(evaluation, output)
    return evaluation


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: SessionFactory | None = None,
    scorer: OpportunityScorer | None = None,
    evaluation_date: date | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    try:
        evaluation = run_evaluation(
            sample_size=args.sample_size,
            session_factory=session_factory,
            scorer=scorer,
            evaluation_date=evaluation_date,
            output=stdout,
        )
    except Exception as exc:
        print(f"Opportunity scorer evaluation failed: {exc}", file=stderr)
        return 1

    if evaluation.consistency_violations:
        print(
            "Opportunity scorer evaluation found structural consistency violations.",
            file=stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
