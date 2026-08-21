import argparse
from collections.abc import Callable, Sequence
from datetime import datetime
import sys
from typing import TextIO

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services.planning_ingestion import (
    InitialPlanningImportRequiredError,
    sync_planning_applications,
)
from . import add_paging_arguments


SyncResult = dict[str, int | datetime]
SessionFactory = Callable[[], Session]
SyncService = Callable[..., SyncResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize planning applications changed since the last import."
    )
    add_paging_arguments(parser)
    return parser


def run_sync(
    *,
    page_size: int,
    max_pages: int | None,
    session_factory: SessionFactory | None = None,
    sync_service: SyncService | None = None,
    output: TextIO | None = None,
) -> SyncResult:
    output = sys.stdout if output is None else output
    session_factory = SessionLocal if session_factory is None else session_factory
    sync_service = sync_planning_applications if sync_service is None else sync_service
    session = session_factory()
    try:
        result = sync_service(
            session,
            page_size=page_size,
            max_pages=max_pages,
        )
    finally:
        session.close()

    watermark = result["watermark"]
    watermark_text = (
        watermark.isoformat() if isinstance(watermark, datetime) else str(watermark)
    )
    print(
        "Planning sync complete: "
        f"watermark used={watermark_text}, "
        f"pages processed={result['pages_processed']}, "
        f"fetched={result['fetched']}, "
        f"inserted={result['inserted']}, "
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
            page_size=args.page_size,
            max_pages=args.max_pages,
            session_factory=session_factory,
            sync_service=sync_service,
            output=stdout,
        )
    except InitialPlanningImportRequiredError as exc:
        print(
            "Planning sync failed: an initial planning import is required. "
            "Run `python -m backend.app.commands.planning_import` first. "
            f"Details: {exc}",
            file=stderr,
        )
        return 1
    except Exception as exc:
        print(f"Planning sync failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
