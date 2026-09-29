"""Password, session, and request protections for customer accounts."""

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request, status

from ..models.user import normalize_email
from .rate_limiting import InMemoryRateLimiter, enforce_rate_limit


SESSION_COOKIE_NAME = "siteforecaster_session"
SESSION_LIFETIME = timedelta(days=7)
password_hasher = PasswordHasher()
_dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))

signup_ip_limiter = InMemoryRateLimiter(limit=5, window_seconds=3600)
signup_email_limiter = InMemoryRateLimiter(limit=3, window_seconds=3600)
login_ip_limiter = InMemoryRateLimiter(limit=10, window_seconds=60)
login_email_limiter = InMemoryRateLimiter(limit=5, window_seconds=900)


@dataclass(frozen=True)
class AuthSettings:
    cookie_secure: bool
    allowed_origins: frozenset[str]


def get_auth_settings() -> AuthSettings:
    environment = os.getenv("APP_ENV", "production").strip().lower()
    secure_setting = os.getenv("AUTH_COOKIE_SECURE", "true").strip().lower()
    if secure_setting not in {"true", "false"}:
        raise RuntimeError("AUTH_COOKIE_SECURE must be true or false.")
    cookie_secure = secure_setting == "true"
    if not cookie_secure and environment != "development":
        raise RuntimeError("Insecure session cookies require APP_ENV=development.")

    origins = frozenset(
        origin.strip()
        for origin in os.getenv("AUTH_ALLOWED_ORIGINS", "https://siteforecaster.com").split(",")
        if origin.strip()
    )
    if not origins:
        raise RuntimeError("AUTH_ALLOWED_ORIGINS must list trusted origins.")
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or origin != f"{parsed.scheme}://{parsed.netloc}"
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and environment != "development")
            or (
                not cookie_secure
                and (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
            )
        ):
            raise RuntimeError("AUTH_ALLOWED_ORIGINS must list trusted origins.")
    return AuthSettings(cookie_secure=cookie_secure, allowed_origins=origins)


def require_trusted_origin(request: Request) -> None:
    """Fail closed on cross-origin or origin-less state changes."""
    origin = request.headers.get("origin")
    if origin not in get_auth_settings().allowed_origins or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted request origin.")


def require_json_request(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="A JSON request is required.",
        )


def enforce_auth_rate_limit(request: Request, email: str, *, signup: bool) -> None:
    ip_limiter = signup_ip_limiter if signup else login_ip_limiter
    email_limiter = signup_email_limiter if signup else login_email_limiter
    detail = "Too many account requests. Please try again later."
    enforce_rate_limit(request, limiter=ip_limiter, detail=detail)
    email_key = hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()
    if not email_limiter.allow(email_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(int(email_limiter.window_seconds))},
        )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        password_hasher.verify(password_hash or _dummy_password_hash, password)
    except (InvalidHashError, VerificationError):
        return False
    return password_hash is not None


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + SESSION_LIFETIME
