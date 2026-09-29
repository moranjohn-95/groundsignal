"""Public account registration and cookie-backed customer sessions."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import User, UserSession
from ..models.user import normalize_email
from ..services import authentication as auth


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=12, max_length=1024)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if email.count("@") != 1 or any(char.isspace() for char in email):
            raise ValueError("Enter a valid email address.")
        local, domain = email.split("@")
        if not local or not domain or "." not in domain:
            raise ValueError("Enter a valid email address.")
        return email


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    created_at: datetime


def _session_for_cookie(session: Session, request: Request) -> UserSession | None:
    token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    if not token:
        return None
    return session.scalar(
        select(UserSession)
        .join(User)
        .where(
            UserSession.token_hash == auth.hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > func.now(),
            User.is_active.is_(True),
        )
    )


def require_current_user(
    request: Request, session: Annotated[Session, Depends(get_db)]
) -> User:
    login_session = _session_for_cookie(session, request)
    if login_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return login_session.user


def _issue_session(session: Session, request: Request, response: Response, user: User) -> None:
    old_token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    if old_token:
        session.execute(
            update(UserSession)
            .where(
                UserSession.token_hash == auth.hash_session_token(old_token),
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )

    token = auth.new_session_token()
    session.add(
        UserSession(user=user, token_hash=auth.hash_session_token(token), expires_at=auth.session_expiry())
    )
    session.commit()
    settings = auth.get_auth_settings()
    response.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=int(auth.SESSION_LIFETIME.total_seconds()),
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/signup", response_model=CurrentUser, status_code=status.HTTP_201_CREATED)
def signup(
    data: SignupRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    _origin: Annotated[None, Depends(auth.require_trusted_origin)],
    _json: Annotated[None, Depends(auth.require_json_request)],
) -> User:
    auth.enforce_auth_rate_limit(request, data.email, signup=True)
    email = normalize_email(data.email)
    if session.scalar(select(User.id).where(func.lower(func.trim(User.email)) == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

    user = User(email=email, password_hash=auth.hash_password(data.password.get_secret_value()))
    session.add(user)
    try:
        session.flush()
        _issue_session(session, request, response, user)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered."
        ) from exc
    session.refresh(user)
    return user


@router.post("/login", response_model=CurrentUser)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    _origin: Annotated[None, Depends(auth.require_trusted_origin)],
    _json: Annotated[None, Depends(auth.require_json_request)],
) -> User:
    auth.enforce_auth_rate_limit(request, data.email, signup=False)
    email = normalize_email(data.email)
    user = session.scalar(select(User).where(func.lower(func.trim(User.email)) == email))
    valid_password = auth.verify_password(
        user.password_hash if user else None, data.password.get_secret_value()
    )
    if not valid_password or user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if auth.password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = auth.hash_password(data.password.get_secret_value())
    _issue_session(session, request, response, user)
    session.refresh(user)
    return user


@router.get("/me", response_model=CurrentUser)
def me(response: Response, user: Annotated[User, Depends(require_current_user)]) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    _origin: Annotated[None, Depends(auth.require_trusted_origin)],
) -> None:
    token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    if token:
        session.execute(
            update(UserSession)
            .where(UserSession.token_hash == auth.hash_session_token(token))
            .values(revoked_at=func.now())
        )
        session.commit()
    response.delete_cookie(auth.SESSION_COOKIE_NAME, path="/")
    response.headers["Cache-Control"] = "no-store"
