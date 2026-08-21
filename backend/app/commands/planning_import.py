import argparse
from collections.abc import Callable, Sequence
import sys
from typing import TextIO

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services.planning_ingestion import ingest_all_planning_applications
from . import add_paging_arguments


ImportResult = dict[str, int]
SessionFactory = Callable[[], Session]
ImportService = Callable[..., ImportResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import all national planning applications into GroundSignal."
    )
    add_paging_arguments(parser)
    return parser


def run_import(
    *,
    page_size: int,
    max_pages: int | None,
    session_factory: SessionFactory | None = None,
    ingestion_service: ImportService | None = None,
    output: TextIO | None = None,
) -> ImportResult:
    output = sys.stdout if output is None else output
    session_factory = SessionLocal if session_factory is None else session_factory
    ingestion_service = (
        ingest_all_planning_applications
        if ingestion_service is None
        else ingestion_service
    )
    session = session_factory()
    try:
        result = ingestion_service(
            session,
            page_size=page_size,
            max_pages=max_pages,
        )
    finally:
        session.close()

    print(
        "Planning import complete: "
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
    ingestion_service: ImportService | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    try:
        run_import(
            page_size=args.page_size,
            max_pages=args.max_pages,
            session_factory=session_factory,
            ingestion_service=ingestion_service,
            output=stdout,
        )
    except Exception as exc:
        print(f"Planning import failed: {exc}", file=stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
