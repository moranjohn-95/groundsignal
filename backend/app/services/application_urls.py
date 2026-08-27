"""Validation for upstream planning-application links."""

from urllib.parse import urlsplit


ALLOWED_APPLICATION_URL_SCHEMES = frozenset({"http", "https"})


def safe_application_url(value: str | None) -> str | None:
    """Return a safe external application URL, or ``None`` when unavailable."""

    if (
        value is None
        or value != value.strip()
        or any(char.isspace() for char in value)
    ):
        return None

    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        return None

    if (
        parsed.scheme.lower() not in ALLOWED_APPLICATION_URL_SCHEMES
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value
