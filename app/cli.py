"""CLI entry point (spec §14 Phase 6: `python -m app.cli backfill-embeddings`).

Usage:
    python -m app.cli backfill-embeddings
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_backfill_embeddings() -> None:
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.services.embeddings import backfill_embeddings  # noqa: PLC0415

    db = SessionLocal()
    try:
        result = backfill_embeddings(db)
        logger.info("backfill complete: %s", result)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="app.cli", description="Enterprise AI Knowledge Assistant CLI")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("backfill-embeddings", help="Embed all chunks that are missing embeddings")

    args = parser.parse_args(argv)
    if args.command == "backfill-embeddings":
        cmd_backfill_embeddings()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
