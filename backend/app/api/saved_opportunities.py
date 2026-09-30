"""Private saved planning opportunities for the current customer."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..dependencies import get_db
from ..models import PlanningApplication, SavedOpportunity, User
from ..schemas.saved_opportunity import (
    SaveOpportunityRequest,
    SavedOpportunityListResponse,
    SavedOpportunityResponse,
)
from ..services import authentication as auth
from .auth import require_current_user
from .planning_applications import PUBLIC_COLUMNS, _planning_application_response


router = APIRouter(prefix="/api/v1/saved-opportunities", tags=["saved-opportunities"])


def _saved_item(saved: SavedOpportunity) -> SavedOpportunityResponse:
    return SavedOpportunityResponse(
        id=saved.id,
        saved_at=saved.saved_at,
        opportunity=_planning_application_response(saved.planning_application),
    )


def _saved_for_user(
    session: Session, *, user_id: int, planning_application_id: int
) -> SavedOpportunity | None:
    return session.scalar(
        select(SavedOpportunity)
        .options(
            selectinload(SavedOpportunity.planning_application).load_only(*PUBLIC_COLUMNS)
        )
        .where(
            SavedOpportunity.user_id == user_id,
            SavedOpportunity.planning_application_id == planning_application_id,
        )
    )


@router.post("", response_model=SavedOpportunityResponse, status_code=status.HTTP_201_CREATED)
def save_opportunity(
    data: SaveOpportunityRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_current_user)],
    _origin: Annotated[None, Depends(auth.require_trusted_origin)],
    _json: Annotated[None, Depends(auth.require_json_request)],
) -> SavedOpportunityResponse:
    if session.scalar(
        select(PlanningApplication.id).where(
            PlanningApplication.id == data.planning_application_id
        )
    ) is None:
        raise HTTPException(status_code=404, detail="Planning opportunity not found.")

    saved = _saved_for_user(
        session, user_id=user.id, planning_application_id=data.planning_application_id
    )
    if saved is not None:
        response.status_code = status.HTTP_200_OK
        return _saved_item(saved)

    session.add(
        SavedOpportunity(user_id=user.id, planning_application_id=data.planning_application_id)
    )
    try:
        session.commit()
    except IntegrityError:
        # A concurrent save may have won the unique (user, planning) constraint.
        session.rollback()
        saved = _saved_for_user(
            session, user_id=user.id, planning_application_id=data.planning_application_id
        )
        if saved is None:
            if session.scalar(
                select(PlanningApplication.id).where(
                    PlanningApplication.id == data.planning_application_id
                )
            ) is None:
                raise HTTPException(status_code=404, detail="Planning opportunity not found.")
            raise
        response.status_code = status.HTTP_200_OK
        return _saved_item(saved)

    saved = _saved_for_user(
        session, user_id=user.id, planning_application_id=data.planning_application_id
    )
    return _saved_item(saved)


@router.get("", response_model=SavedOpportunityListResponse)
def list_saved_opportunities(
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SavedOpportunityListResponse:
    total = session.scalar(
        select(func.count(SavedOpportunity.id)).where(SavedOpportunity.user_id == user.id)
    ) or 0
    statement = (
        select(SavedOpportunity)
        .options(
            selectinload(SavedOpportunity.planning_application).load_only(*PUBLIC_COLUMNS)
        )
        .where(SavedOpportunity.user_id == user.id)
        .order_by(SavedOpportunity.saved_at.desc(), SavedOpportunity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return SavedOpportunityListResponse(
        items=[_saved_item(saved) for saved in session.scalars(statement).all()],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.delete("/{save_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_opportunity(
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_current_user)],
    _origin: Annotated[None, Depends(auth.require_trusted_origin)],
    save_id: Annotated[int, Path(gt=0)],
) -> None:
    saved = session.scalar(
        select(SavedOpportunity).where(
            SavedOpportunity.id == save_id,
            SavedOpportunity.user_id == user.id,
        )
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved opportunity not found.")
    session.delete(saved)
    session.commit()
