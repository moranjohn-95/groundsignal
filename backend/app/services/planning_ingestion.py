from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PlanningApplication
from .planning_api import fetch_planning_applications
from .planning_transformer import transform_planning_application


DATABASE_MANAGED_FIELDS = {"id", "created_at", "updated_at"}


def ingest_planning_applications(session: Session, limit: int = 5) -> dict[str, int]:
    try:
        features = fetch_planning_applications(limit)
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

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "fetched": len(features),
        "inserted": inserted_count,
        "updated": updated_count,
    }
