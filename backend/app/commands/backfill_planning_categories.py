import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
from typing import TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only
from sqlalchemy.sql import Select

from ..database import SessionLocal
from ..models import PlanningApplication
from ..services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
    PlanningApplicationCategory,
    classify_planning_application,
)


DEFAULT_BATCH_SIZE = 1000

SessionFactory = Callable[[], Session]
Classifier = Callable[..., PlanningApplicationCategory]


@dataclass(frozen=True)
class BackfillResult:
    batches_completed: int
    records_categorised: int
    category_counts: dict[PlanningApplicationCategory, int]
    uncategorised_records_remain: bool


def _validate_options(batch_size: int, max_batches: int | None) -> None:
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size <= 0
    ):
        raise ValueError("batch_size must be a positive integer")
    if (
        max_batches is not None
        and (
            isinstance(max_batches, bool)
            or not isinstance(max_batches, int)
            or max_batches <= 0
        )
    ):
        raise ValueError("max_batches must be None or a positive integer")


def _positive_integer_argument(value: str, *, name: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{name} must be a positive integer"
        ) from exc

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(f"{name} must be a positive integer")
    return parsed_value


def _batch_size_argument(value: str) -> int:
    return _positive_integer_argument(value, name="batch size")


def _max_batches_argument(value: str) -> int:
    return _positive_integer_argument(value, name="max batches")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill persisted planning-application categories in batches."
    )
    parser.add_argument(
        "--batch-size",
        type=_batch_size_argument,
        default=DEFAULT_BATCH_SIZE,
        help=f"records to categorise per transaction (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-batches",
        type=_max_batches_argument,
        default=None,
        help="stop after this many committed batches",
    )
    return parser


def build_batch_statement(
    batch_size: int,
    after_id: int | None = None,
) -> Select:
    _validate_options(batch_size, None)
    statement = (
        select(PlanningApplication)
        .options(
            load_only(
                PlanningApplication.id,
                PlanningApplication.description,
                PlanningApplication.application_type,
                PlanningApplication.number_residential_units,
                PlanningApplication.floor_area,
                PlanningApplication.category,
            )
        )
        .where(PlanningApplication.category.is_(None))
    )
    if after_id is not None:
        statement = statement.where(PlanningApplication.id > after_id)
    return (
        statement.order_by(PlanningApplication.id.asc())
        .limit(batch_size)
        .with_for_update()
    )


def load_uncategorised_batch(
    session: Session,
    batch_size: int,
    after_id: int | None,
) -> list[PlanningApplication]:
    statement = build_batch_statement(batch_size, after_id)
    return list(session.scalars(statement).all())


def has_uncategorised_records(session: Session) -> bool:
    statement = (
        select(PlanningApplication.id)
        .where(PlanningApplication.category.is_(None))
        .order_by(PlanningApplication.id.asc())
        .limit(1)
    )
    return session.scalar(statement) is not None


def backfill_planning_categories(
    session: Session,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int | None = None,
    classifier: Classifier = classify_planning_application,
    output: TextIO | None = None,
) -> BackfillResult:
    _validate_options(batch_size, max_batches)
    output = sys.stdout if output is None else output
    category_counts = {
        category: 0 for category in PLANNING_APPLICATION_CATEGORIES
    }
    batches_completed = 0
    records_categorised = 0
    last_committed_id: int | None = None

    while max_batches is None or batches_completed < max_batches:
        try:
            batch = load_uncategorised_batch(
                session,
                batch_size,
                last_committed_id,
            )
            if not batch:
                return BackfillResult(
                    batches_completed=batches_completed,
                    records_categorised=records_categorised,
                    category_counts=category_counts,
                    uncategorised_records_remain=False,
                )

            batch_counts = {
                category: 0 for category in PLANNING_APPLICATION_CATEGORIES
            }
            for application in batch:
                category = classifier(
                    description=application.description,
                    application_type=application.application_type,
                    number_residential_units=(
                        application.number_residential_units
                    ),
                    floor_area=application.floor_area,
                )
                application.category = category
                batch_counts[category] += 1
            session.commit()
        except Exception:
            session.rollback()
            raise

        last_committed_id = batch[-1].id
        batches_completed += 1
        records_categorised += len(batch)
        for category, count in batch_counts.items():
            category_counts[category] += count

        print(
            f"Batch {batches_completed} complete: "
            f"records categorised={len(batch)}, "
            f"total categorised={records_categorised}",
            file=output,
        )

    try:
        uncategorised_records_remain = has_uncategorised_records(session)
    except Exception:
        session.rollback()
        raise

    return BackfillResult(
        batches_completed=batches_completed,
        records_categorised=records_categorised,
        category_counts=category_counts,
        uncategorised_records_remain=uncategorised_records_remain,
    )


def print_summary(
    result: BackfillResult,
    output: TextIO | None = None,
) -> None:
    output = sys.stdout if output is None else output
    remain = "yes" if result.uncategorised_records_remain else "no"
    print(
        "Planning category backfill complete: "
        f"batches completed={result.batches_completed}, "
        f"records categorised={result.records_categorised}, "
        f"uncategorised records remain={remain}",
        file=output,
    )
    print(
        "Category counts: "
        + ", ".join(
            f"{category}={result.category_counts[category]}"
            for category in PLANNING_APPLICATION_CATEGORIES
        ),
        file=output,
    )


def run_backfill(
    *,
    batch_size: int,
    max_batches: int | None,
    session_factory: SessionFactory | None = None,
    classifier: Classifier | None = None,
    output: TextIO | None = None,
) -> BackfillResult:
    session_factory = SessionLocal if session_factory is None else session_factory
    classifier = classify_planning_application if classifier is None else classifier
    session = session_factory()
    try:
        result = backfill_planning_categories(
            session,
            batch_size=batch_size,
            max_batches=max_batches,
            classifier=classifier,
            output=output,
        )
    finally:
        session.close()

    print_summary(result, output)
    return result


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
        run_backfill(
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            session_factory=session_factory,
            classifier=classifier,
            output=stdout,
        )
    except Exception as exc:
        print(f"Planning category backfill failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
