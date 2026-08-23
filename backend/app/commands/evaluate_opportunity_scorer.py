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
DESCRIPTION_MAX_LENGTH = 110

OPPORTUNITY_LEVELS: tuple[OpportunityLevel, ...] = (
    "very_high",
    "high",
    "medium",
    "low",
    "very_low",
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
    return OpportunityScorerEvaluation(
        evaluated_on=evaluation_date,
        results=tuple(scored_records),
        level_counts=level_counts,
        average_score=sum(scores) / len(scores) if scores else 0.0,
        minimum_score=min(scores) if scores else None,
        maximum_score=max(scores) if scores else None,
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
        f"score={score.opportunity_score} | "
        f"level={score.opportunity_level} | "
        f"description={_shorten_description(application.description)}",
        file=output,
    )


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
        run_evaluation(
            sample_size=args.sample_size,
            session_factory=session_factory,
            scorer=scorer,
            evaluation_date=evaluation_date,
            output=stdout,
        )
    except Exception as exc:
        print(f"Opportunity scorer evaluation failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
