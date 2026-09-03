import argparse
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta, timezone
import sys
from typing import TextIO

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services.planning_ingestion import sync_planning_applications
from . import add_paging_arguments


DEFAULT_SYNC_WINDOW_DAYS = 7
SyncResult = dict[str, int]
SessionFactory = Callable[[], Session]
SyncService = Callable[..., SyncResult]


def _days_argument(value: str) -> int:
    try:
        days = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("days must be an integer") from exc

    if days <= 0:
        raise argparse.ArgumentTypeError("days must be a positive integer")
    return days


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize planning applications received in a rolling date window."
    )
    add_paging_arguments(parser)
    parser.add_argument(
        "--days",
        type=_days_argument,
        default=DEFAULT_SYNC_WINDOW_DAYS,
        help=(
            "sync applications received within this many days of the current "
            f"UTC date (default: {DEFAULT_SYNC_WINDOW_DAYS})"
        ),
    )
    return parser


def run_sync(
    *,
    days: int,
    page_size: int,
    max_pages: int | None,
    session_factory: SessionFactory | None = None,
    sync_service: SyncService | None = None,
    output: TextIO | None = None,
) -> SyncResult:
    output = sys.stdout if output is None else output
    session_factory = SessionLocal if session_factory is None else session_factory
    sync_service = sync_planning_applications if sync_service is None else sync_service
    # Re-read an inclusive ReceivedDate window; upserts make the overlap safe.
    since = _current_utc_date() - timedelta(days=days)
    session = session_factory()
    try:
        result = sync_service(
            session,
            since=since,
            page_size=page_size,
            max_pages=max_pages,
        )
    finally:
        session.close()

    print(
        "Planning sync complete:\n"
        f"window days={days}\n"
        f"since={since.isoformat()}\n"
        f"pages processed={result['pages_processed']}\n"
        f"fetched={result['fetched']}\n"
        f"inserted={result['inserted']}\n"
        f"updated={result['updated']}",
        file=output,
    )
    return result


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: SessionFactory | None = None,
    sync_service: SyncService | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    try:
        run_sync(
            days=args.days,
            page_size=args.page_size,
            max_pages=args.max_pages,
            session_factory=session_factory,
            sync_service=sync_service,
            output=stdout,
        )
    except Exception as exc:
        print(f"Planning sync failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
