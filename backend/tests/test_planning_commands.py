from datetime import datetime, timezone
from io import StringIO
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from backend.app.commands import planning_import, planning_sync
from backend.app.services.planning_ingestion import (
    InitialPlanningImportRequiredError,
)


IMPORT_RESULT = {
    "pages_processed": 3,
    "fetched": 1200,
    "inserted": 1100,
    "updated": 100,
}
SYNC_WATERMARK = datetime(2026, 8, 20, 12, 30, tzinfo=timezone.utc)
SYNC_RESULT = {
    "watermark": SYNC_WATERMARK,
    "pages_processed": 2,
    "fetched": 125,
    "inserted": 25,
    "updated": 100,
}


def test_import_command_uses_defaults_and_prints_summary() -> None:
    session = Mock(spec=Session)
    session_factory = Mock(return_value=session)
    ingestion_service = Mock(return_value=IMPORT_RESULT)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = planning_import.main(
        [],
        session_factory=session_factory,
        ingestion_service=ingestion_service,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    session_factory.assert_called_once_with()
    ingestion_service.assert_called_once_with(
        session,
        page_size=500,
        max_pages=None,
    )
    session.close.assert_called_once_with()
    assert stdout.getvalue() == (
        "Planning import complete: pages processed=3, fetched=1200, "
        "inserted=1100, updated=100\n"
    )
    assert stderr.getvalue() == ""


def test_import_command_passes_custom_page_size_and_max_pages() -> None:
    session = Mock(spec=Session)
    ingestion_service = Mock(return_value=IMPORT_RESULT)

    exit_code = planning_import.main(
        ["--page-size", "750", "--max-pages", "4"],
        session_factory=Mock(return_value=session),
        ingestion_service=ingestion_service,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    ingestion_service.assert_called_once_with(
        session,
        page_size=750,
        max_pages=4,
    )
    session.close.assert_called_once_with()


def test_import_runner_closes_session_and_preserves_failure() -> None:
    session = Mock(spec=Session)
    failure = RuntimeError("ArcGIS unavailable")

    with pytest.raises(RuntimeError) as exc_info:
        planning_import.run_import(
            page_size=500,
            max_pages=None,
            session_factory=Mock(return_value=session),
            ingestion_service=Mock(side_effect=failure),
            output=StringIO(),
        )

    assert exc_info.value is failure
    session.close.assert_called_once_with()


def test_import_command_failure_returns_nonzero_and_writes_stderr() -> None:
    session = Mock(spec=Session)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = planning_import.main(
        [],
        session_factory=Mock(return_value=session),
        ingestion_service=Mock(side_effect=RuntimeError("database unavailable")),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Planning import failed: database unavailable\n"
    session.close.assert_called_once_with()


def test_sync_command_uses_defaults_and_prints_summary() -> None:
    session = Mock(spec=Session)
    session_factory = Mock(return_value=session)
    sync_service = Mock(return_value=SYNC_RESULT)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = planning_sync.main(
        [],
        session_factory=session_factory,
        sync_service=sync_service,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    session_factory.assert_called_once_with()
    sync_service.assert_called_once_with(
        session,
        page_size=500,
        max_pages=None,
    )
    session.close.assert_called_once_with()
    assert stdout.getvalue() == (
        "Planning sync complete: watermark used=2026-08-20T12:30:00+00:00, "
        "pages processed=2, fetched=125, inserted=25, updated=100\n"
    )
    assert stderr.getvalue() == ""


def test_sync_command_passes_custom_page_size_and_max_pages() -> None:
    session = Mock(spec=Session)
    sync_service = Mock(return_value=SYNC_RESULT)

    exit_code = planning_sync.main(
        ["--page-size", "1000", "--max-pages", "2"],
        session_factory=Mock(return_value=session),
        sync_service=sync_service,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    sync_service.assert_called_once_with(
        session,
        page_size=1000,
        max_pages=2,
    )
    session.close.assert_called_once_with()


def test_sync_runner_closes_session_and_preserves_failure() -> None:
    session = Mock(spec=Session)
    failure = RuntimeError("sync failed")

    with pytest.raises(RuntimeError) as exc_info:
        planning_sync.run_sync(
            page_size=500,
            max_pages=None,
            session_factory=Mock(return_value=session),
            sync_service=Mock(side_effect=failure),
            output=StringIO(),
        )

    assert exc_info.value is failure
    session.close.assert_called_once_with()


def test_sync_command_missing_initial_import_returns_clear_error() -> None:
    session = Mock(spec=Session)
    stdout = StringIO()
    stderr = StringIO()
    failure = InitialPlanningImportRequiredError("No watermark is available.")

    exit_code = planning_sync.main(
        [],
        session_factory=Mock(return_value=session),
        sync_service=Mock(side_effect=failure),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    error = stderr.getvalue()
    assert "initial planning import is required" in error
    assert "python -m backend.app.commands.planning_import" in error
    assert "No watermark is available." in error
    session.close.assert_called_once_with()


def test_sync_command_other_failure_returns_nonzero() -> None:
    session = Mock(spec=Session)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = planning_sync.main(
        [],
        session_factory=Mock(return_value=session),
        sync_service=Mock(side_effect=RuntimeError("database unavailable")),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Planning sync failed: database unavailable\n"
    session.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--page-size", "0"),
        ("--page-size", "-1"),
        ("--page-size", "2001"),
        ("--page-size", "true"),
        ("--page-size", "1.5"),
        ("--max-pages", "0"),
        ("--max-pages", "-1"),
        ("--max-pages", "false"),
        ("--max-pages", "1.5"),
    ],
)
@pytest.mark.parametrize(
    "build_parser",
    [planning_import.build_parser, planning_sync.build_parser],
)
def test_command_parsers_reject_invalid_numeric_arguments(
    build_parser,
    option: str,
    value: str,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args([option, value])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("page_size", [1, 2000])
@pytest.mark.parametrize(
    "build_parser",
    [planning_import.build_parser, planning_sync.build_parser],
)
def test_command_parsers_accept_supported_page_size_boundaries(
    build_parser,
    page_size: int,
) -> None:
    args = build_parser().parse_args(["--page-size", str(page_size)])

    assert args.page_size == page_size
