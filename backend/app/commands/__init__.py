import argparse


DEFAULT_PAGE_SIZE = 500
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 2000


def _integer_argument(value: str, *, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc


def _page_size_argument(value: str) -> int:
    page_size = _integer_argument(value, name="page size")
    if not MIN_PAGE_SIZE <= page_size <= MAX_PAGE_SIZE:
        raise argparse.ArgumentTypeError(
            f"page size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}"
        )
    return page_size


def _max_pages_argument(value: str) -> int:
    max_pages = _integer_argument(value, name="max pages")
    if max_pages <= 0:
        raise argparse.ArgumentTypeError("max pages must be a positive integer")
    return max_pages


def add_paging_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page-size",
        type=_page_size_argument,
        default=DEFAULT_PAGE_SIZE,
        help=(
            "number of records requested per page "
            f"(default: {DEFAULT_PAGE_SIZE}; range: "
            f"{MIN_PAGE_SIZE}-{MAX_PAGE_SIZE})"
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=_max_pages_argument,
        default=None,
        help="stop after this many pages (development and testing only)",
    )
