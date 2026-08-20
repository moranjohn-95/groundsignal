from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import PlanningApplication
from .planning_api import (
    fetch_planning_applications,
    iter_planning_application_pages,
    iter_planning_application_pages_since,
)
from .planning_transformer import transform_planning_application


DATABASE_MANAGED_FIELDS = {"id", "created_at", "updated_at"}


class InitialPlanningImportRequiredError(RuntimeError):
    """Raised when incremental sync is attempted before an initial import."""


def _persist_planning_application_page(
    session: Session,
    features: list[dict],
) -> dict[str, int]:
    applications_by_source_id: dict[int, PlanningApplication] = {}
    inserted_count = 0
    updated_count = 0

    for feature in features:
        transformed = transform_planning_application(feature)
        source_values = {
            field_name: value
            for field_name, value in transformed.items()
            if field_name not in DATABASE_MANAGED_FIELDS
        }
        source_object_id = source_values["source_object_id"]

        if source_object_id in applications_by_source_id:
            application = applications_by_source_id[source_object_id]
            for field_name, value in source_values.items():
                setattr(application, field_name, value)
            continue

        application = session.scalar(
            select(PlanningApplication).where(
                PlanningApplication.source_object_id == source_object_id
            )
        )

        if application is None:
            application = PlanningApplication(**source_values)
            session.add(application)
            inserted_count += 1
        else:
            for field_name, value in source_values.items():
                setattr(application, field_name, value)
            updated_count += 1

        applications_by_source_id[source_object_id] = application

    return {
        "fetched": len(features),
        "inserted": inserted_count,
        "updated": updated_count,
    }


def ingest_planning_applications(session: Session, limit: int = 5) -> dict[str, int]:
    try:
        features = fetch_planning_applications(limit)
        result = _persist_planning_application_page(session, features)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return result


def _validate_max_pages(max_pages: int | None) -> None:
    if (
        max_pages is not None
        and (
            isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or max_pages <= 0
        )
    ):
        raise ValueError("max_pages must be None or a positive integer")


def _ingest_planning_application_pages(
    session: Session,
    pages: Iterable[list[dict]],
    max_pages: int | None,
) -> dict[str, int]:
    totals = {
        "pages_processed": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
    }

    for features in pages:
        try:
            page_result = _persist_planning_application_page(session, features)
            session.commit()
        except Exception:
            session.rollback()
            raise

        totals["pages_processed"] += 1
        totals["fetched"] += page_result["fetched"]
        totals["inserted"] += page_result["inserted"]
        totals["updated"] += page_result["updated"]

        if max_pages is not None and totals["pages_processed"] >= max_pages:
            break

    return totals


def ingest_all_planning_applications(
    session: Session,
    page_size: int = 500,
    max_pages: int | None = None,
) -> dict[str, int]:
    _validate_max_pages(max_pages)
    pages = iter_planning_application_pages(page_size)
    return _ingest_planning_application_pages(session, pages, max_pages)


def sync_planning_applications(
    session: Session,
    page_size: int = 500,
    max_pages: int | None = None,
) -> dict[str, int | datetime]:
    _validate_max_pages(max_pages)

    watermark = session.scalar(select(func.max(PlanningApplication.source_updated_at)))
    if watermark is None:
        raise InitialPlanningImportRequiredError(
            "Incremental planning sync requires an initial import to be completed first."
        )

    watermark_utc = watermark.astimezone(timezone.utc)
    pages = iter_planning_application_pages_since(watermark_utc, page_size)
    totals = _ingest_planning_application_pages(session, pages, max_pages)

    return {"watermark": watermark_utc, **totals}
