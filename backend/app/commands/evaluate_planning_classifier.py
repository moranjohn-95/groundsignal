import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
from typing import TextIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ..database import SessionLocal
from ..models import PlanningApplication
from ..services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
    PlanningApplicationCategory,
    classify_planning_application,
)


DEFAULT_SAMPLE_SIZE = 500
MIN_SAMPLE_SIZE = 1
MAX_SAMPLE_SIZE = 5000
MAX_EXAMPLES_PER_CATEGORY = 5
DESCRIPTION_MAX_LENGTH = 120

SessionFactory = Callable[[], Session]
Classifier = Callable[..., PlanningApplicationCategory]


@dataclass(frozen=True)
class SampledPlanningApplication:
    id: int
    application_number: str
    description: str | None
    application_type: str | None
    number_residential_units: int | None
    floor_area: float | None


@dataclass(frozen=True)
class ClassifierEvaluation:
    total_evaluated: int
    category_counts: dict[PlanningApplicationCategory, int]
    representative_examples: dict[
        PlanningApplicationCategory,
        list[SampledPlanningApplication],
    ]


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
            "Evaluate the planning classifier against a deterministic database sample."
        )
    )
    parser.add_argument(
        "--sample-size",
        type=_sample_size_argument,
        default=DEFAULT_SAMPLE_SIZE,
        help=(
            f"number of records to evaluate (default: {DEFAULT_SAMPLE_SIZE}; "
            f"range: {MIN_SAMPLE_SIZE}-{MAX_SAMPLE_SIZE})"
        ),
    )
    return parser


def build_sample_statement(sample_size: int) -> Select:
    sample_size = _validate_sample_size(sample_size)
    sample_bucket = func.ntile(sample_size).over(
        order_by=PlanningApplication.id.asc()
    ).label("sample_bucket")
    bucketed_applications = select(
        PlanningApplication.id,
        PlanningApplication.application_number,
        PlanningApplication.description,
        PlanningApplication.application_type,
        PlanningApplication.number_residential_units,
        PlanningApplication.floor_area,
        sample_bucket,
    ).subquery()

    return (
        select(
            bucketed_applications.c.id,
            bucketed_applications.c.application_number,
            bucketed_applications.c.description,
            bucketed_applications.c.application_type,
            bucketed_applications.c.number_residential_units,
            bucketed_applications.c.floor_area,
        )
        .distinct(bucketed_applications.c.sample_bucket)
        .order_by(
            bucketed_applications.c.sample_bucket.asc(),
            bucketed_applications.c.id.asc(),
        )
    )


def load_deterministic_sample(
    session: Session,
    sample_size: int,
) -> list[SampledPlanningApplication]:
    statement = build_sample_statement(sample_size)
    rows = session.execute(statement).mappings().all()
    return [SampledPlanningApplication(**row) for row in rows]


def evaluate_sample(
    records: Sequence[SampledPlanningApplication],
    classifier: Classifier = classify_planning_application,
) -> ClassifierEvaluation:
    category_counts = {
        category: 0 for category in PLANNING_APPLICATION_CATEGORIES
    }
    representative_examples = {
        category: [] for category in PLANNING_APPLICATION_CATEGORIES
    }

    for record in records:
        category = classifier(
            description=record.description,
            application_type=record.application_type,
            number_residential_units=record.number_residential_units,
            floor_area=record.floor_area,
        )
        category_counts[category] += 1
        examples = representative_examples[category]
        if len(examples) < MAX_EXAMPLES_PER_CATEGORY:
            examples.append(record)

    return ClassifierEvaluation(
        total_evaluated=len(records),
        category_counts=category_counts,
        representative_examples=representative_examples,
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


def print_evaluation(
    evaluation: ClassifierEvaluation,
    output: TextIO | None = None,
) -> None:
    output = sys.stdout if output is None else output
    print("Planning classifier evaluation", file=output)
    print(f"Total evaluated: {evaluation.total_evaluated}", file=output)
    print("", file=output)
    print("Category distribution:", file=output)

    for category in PLANNING_APPLICATION_CATEGORIES:
        count = evaluation.category_counts[category]
        percentage = (
            count / evaluation.total_evaluated * 100
            if evaluation.total_evaluated
            else 0.0
        )
        print(f"  {category}: {count} ({percentage:.1f}%)", file=output)

    print("", file=output)
    print("Representative examples:", file=output)
    for category in PLANNING_APPLICATION_CATEGORIES:
        print(f"  {category}:", file=output)
        examples = evaluation.representative_examples[category]
        if not examples:
            print("    (none)", file=output)
            continue
        for record in examples:
            description = _shorten_description(record.description)
            print(
                f"    id={record.id} | "
                f"application_number={record.application_number} | "
                f"category={category} | "
                f"description={description}",
                file=output,
            )


def run_evaluation(
    *,
    sample_size: int,
    session_factory: SessionFactory | None = None,
    classifier: Classifier | None = None,
    output: TextIO | None = None,
) -> ClassifierEvaluation:
    session_factory = SessionLocal if session_factory is None else session_factory
    classifier = classify_planning_application if classifier is None else classifier
    session = session_factory()
    try:
        records = load_deterministic_sample(session, sample_size)
        evaluation = evaluate_sample(records, classifier)
    finally:
        session.close()

    print_evaluation(evaluation, output)
    return evaluation


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: SessionFactory | None = None,
    classifier: Classifier | None = None,
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
            classifier=classifier,
            output=stdout,
        )
    except Exception as exc:
        print(f"Planning classifier evaluation failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
