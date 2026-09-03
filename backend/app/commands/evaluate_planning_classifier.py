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


@dataclass(frozen=True)
class ClassifierBenchmarkCase:
    """A labelled regression case used to measure classifier accuracy."""

    name: str
    description: str | None
    expected_category: PlanningApplicationCategory
    application_type: str | None = None
    number_residential_units: int | None = None
    floor_area: float | None = None


@dataclass(frozen=True)
class ClassifierBenchmarkResult:
    total_evaluated: int
    correct_classifications: int
    incorrect_classifications: int
    category_totals: dict[PlanningApplicationCategory, int]
    category_correct: dict[PlanningApplicationCategory, int]
    misclassifications: list[
        tuple[ClassifierBenchmarkCase, PlanningApplicationCategory]
    ]


CLASSIFIER_BENCHMARK_CASES: tuple[ClassifierBenchmarkCase, ...] = (
    ClassifierBenchmarkCase(
        name="new dwelling",
        description=(
            "Construction of a dwelling, domestic garage, proprietary effluent "
            "treatment system and associated site works."
        ),
        expected_category="residential",
    ),
    ClassifierBenchmarkCase(
        name="warehouse-to-apartments conversion",
        description="Conversion of an existing warehouse to eight apartments.",
        expected_category="residential",
    ),
    ClassifierBenchmarkCase(
        name="dwelling with roof-mounted photovoltaic panels",
        description=(
            "Construction of a detached dwelling with ancillary roof-mounted "
            "photovoltaic panels."
        ),
        expected_category="residential",
    ),
    ClassifierBenchmarkCase(
        name="shop replacement dwelling",
        description="Demolition of an existing shop and construction of one dwelling.",
        expected_category="residential",
    ),
    ClassifierBenchmarkCase(
        name="retail store and offices",
        description="Construction of a single-storey discount retail store and offices.",
        expected_category="commercial",
    ),
    ClassifierBenchmarkCase(
        name="home-to-office change of use",
        description="Change of use of an existing dwelling house to an office.",
        expected_category="commercial",
    ),
    ClassifierBenchmarkCase(
        name="warehouse-to-retail conversion",
        description="Conversion of warehouse to retail store.",
        expected_category="commercial",
    ),
    ClassifierBenchmarkCase(
        name="guesthouse alterations",
        description="Alterations to an existing guesthouse.",
        expected_category="commercial",
    ),
    ClassifierBenchmarkCase(
        name="warehouse and manufacturing extension",
        description="Extension to an existing warehouse and manufacturing facility.",
        expected_category="industrial",
    ),
    ClassifierBenchmarkCase(
        name="standalone warehouse",
        description="Construction of a standalone warehouse.",
        expected_category="industrial",
    ),
    ClassifierBenchmarkCase(
        name="light-industrial change of use",
        description="Change of use of an existing building to light industrial use.",
        expected_category="industrial",
    ),
    ClassifierBenchmarkCase(
        name="warehouse and offices",
        description="Construction of warehouse and associated offices.",
        expected_category="industrial",
    ),
    ClassifierBenchmarkCase(
        name="haulage workshop with public-road entrance",
        description=(
            "Construction of a single-storey workshop for a haulage business "
            "with a new entrance from the public road."
        ),
        expected_category="industrial",
    ),
    ClassifierBenchmarkCase(
        name="solar development with battery storage",
        description=(
            "A 10-year solar photovoltaic development with battery storage."
        ),
        expected_category="energy",
    ),
    ClassifierBenchmarkCase(
        name="standalone solar farm",
        description="Development of a standalone solar farm.",
        expected_category="energy",
    ),
    ClassifierBenchmarkCase(
        name="wind farm",
        description="Development of a wind farm and associated roads.",
        expected_category="energy",
    ),
    ClassifierBenchmarkCase(
        name="standalone electricity substation",
        description="Construction of a standalone ESB substation and switch room.",
        expected_category="energy",
    ),
    ClassifierBenchmarkCase(
        name="wastewater and bridge upgrade",
        description=(
            "Upgrade of wastewater and water infrastructure, including a bridge."
        ),
        expected_category="infrastructure",
    ),
    ClassifierBenchmarkCase(
        name="public cycleway",
        description="Construction of a public cycleway and associated road works.",
        expected_category="infrastructure",
    ),
    ClassifierBenchmarkCase(
        name="forest access road",
        description="Construction of a forest access road.",
        expected_category="infrastructure",
    ),
    ClassifierBenchmarkCase(
        name="wastewater treatment works",
        description="Upgrade of wastewater treatment and sludge drying works.",
        expected_category="infrastructure",
    ),
    ClassifierBenchmarkCase(
        name="retail and apartments",
        description="Mixed-use development comprising a shop and eight apartments.",
        expected_category="mixed_use",
    ),
    ClassifierBenchmarkCase(
        name="retail with apartments",
        description="Ground-floor retail unit with six apartments on upper floors.",
        expected_category="mixed_use",
    ),
    ClassifierBenchmarkCase(
        name="offices with apartments",
        description=(
            "Mixed-use development with ground-floor offices and apartments "
            "on upper floors."
        ),
        expected_category="mixed_use",
    ),
    ClassifierBenchmarkCase(
        name="commercial units and apartments",
        description="Commercial units and apartments in a mixed-use development.",
        expected_category="mixed_use",
    ),
    ClassifierBenchmarkCase(
        name="agricultural storage shed",
        description="Retention of an agricultural storage shed and associated site works.",
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="natural gas enclosure",
        description="Construction of a natural gas pressure reduction enclosure.",
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="sports ground development",
        description="Development of a sports ground with changing rooms.",
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="telecommunications cabinet",
        description="Installation of a broadband telecommunications cabinet.",
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="attic conversion on a road address",
        description="Retention of a conversion of attic space at Blackrock Road, Cork.",
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="extension on a road address",
        description=(
            "Construction of an extension and internal alterations at "
            "Carleton Road, Dublin."
        ),
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="mews refurbishment with photovoltaic panels",
        description=(
            "Refurbishment of a protected mews building with roof lights and "
            "photovoltaic panels."
        ),
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="minor amendment with ESB substation",
        description=(
            "Minor alterations to a previously approved sports-pitch "
            "development, including an ESB substation."
        ),
        expected_category="other",
    ),
    ClassifierBenchmarkCase(
        name="agricultural entrance from a public road",
        description=(
            "Permission to construct an agricultural slatted shed and a new "
            "farmyard entrance from the public road."
        ),
        expected_category="other",
    ),
)


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
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help=(
            "evaluate the curated labelled regression benchmark instead of "
            "a database sample"
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


def evaluate_benchmark(
    cases: Sequence[ClassifierBenchmarkCase] = CLASSIFIER_BENCHMARK_CASES,
    classifier: Classifier = classify_planning_application,
) -> ClassifierBenchmarkResult:
    """Compare deterministic classifier output with curated expected categories."""

    category_totals = {
        category: 0 for category in PLANNING_APPLICATION_CATEGORIES
    }
    category_correct = {
        category: 0 for category in PLANNING_APPLICATION_CATEGORIES
    }
    misclassifications = []

    for case in cases:
        category_totals[case.expected_category] += 1
        actual_category = classifier(
            description=case.description,
            application_type=case.application_type,
            number_residential_units=case.number_residential_units,
            floor_area=case.floor_area,
        )
        if actual_category == case.expected_category:
            category_correct[case.expected_category] += 1
        else:
            misclassifications.append((case, actual_category))

    total_evaluated = len(cases)
    incorrect_classifications = len(misclassifications)
    return ClassifierBenchmarkResult(
        total_evaluated=total_evaluated,
        correct_classifications=total_evaluated - incorrect_classifications,
        incorrect_classifications=incorrect_classifications,
        category_totals=category_totals,
        category_correct=category_correct,
        misclassifications=misclassifications,
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


def print_benchmark_evaluation(
    evaluation: ClassifierBenchmarkResult,
    output: TextIO | None = None,
) -> None:
    """Print the labelled benchmark result in a terminal-friendly format."""

    output = sys.stdout if output is None else output
    accuracy = (
        evaluation.correct_classifications / evaluation.total_evaluated * 100
        if evaluation.total_evaluated
        else 0.0
    )
    print("Planning classifier benchmark", file=output)
    print(f"Total evaluated: {evaluation.total_evaluated}", file=output)
    print(
        f"Correct classifications: {evaluation.correct_classifications}",
        file=output,
    )
    print(
        f"Incorrect classifications: {evaluation.incorrect_classifications}",
        file=output,
    )
    print(f"Overall accuracy: {accuracy:.1f}%", file=output)
    print("", file=output)
    print("Category breakdown:", file=output)

    for category in PLANNING_APPLICATION_CATEGORIES:
        total = evaluation.category_totals[category]
        correct = evaluation.category_correct[category]
        percentage = correct / total * 100 if total else 0.0
        print(
            f"  {category}: {correct}/{total} correct ({percentage:.1f}%)",
            file=output,
        )

    print("", file=output)
    print("Misclassifications:", file=output)
    if not evaluation.misclassifications:
        print("  (none)", file=output)
        return

    for case, actual_category in evaluation.misclassifications:
        print(
            f"  {case.name}: expected={case.expected_category} "
            f"actual={actual_category}",
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


def run_benchmark(
    *,
    classifier: Classifier | None = None,
    output: TextIO | None = None,
) -> ClassifierBenchmarkResult:
    classifier = classify_planning_application if classifier is None else classifier
    evaluation = evaluate_benchmark(classifier=classifier)
    print_benchmark_evaluation(evaluation, output)
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
        if args.benchmark:
            run_benchmark(classifier=classifier, output=stdout)
        else:
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
