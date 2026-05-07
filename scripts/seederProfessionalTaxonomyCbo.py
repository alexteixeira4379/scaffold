"""Seeder for the professional taxonomy tables using the CBO 2002 dataset.

Usage:
    python scripts/seederProfessionalTaxonomyCbo.py
    python scripts/seederProfessionalTaxonomyCbo.py --dataset-dir /path/to/csvs
    python scripts/seederProfessionalTaxonomyCbo.py --source cbo
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

importlib.import_module("scaffold.models")

_DEFAULT_DATASET_DIR = str(_ROOT / "migrations" / "core" / "seeders" / "estrutura-cbo")

from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.professional.cbo_importer import CboImporter  # noqa: E402


async def run(dataset_dir: str, source: str) -> None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            importer = CboImporter(session, Path(dataset_dir), source=source)
            stats = await importer.run()

        print("\n=== CBO Import Summary ===")
        for key, count in stats.items():
            print(f"  {key:30s}: {count:>8,}")
        print("==========================\n")
    finally:
        await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed professional taxonomy from CBO dataset")
    parser.add_argument(
        "--dataset-dir",
        default=_DEFAULT_DATASET_DIR,
        dest="dataset_dir",
        help="Path to CBO CSV directory",
    )
    parser.add_argument(
        "--source",
        default="cbo",
        help="Source label written to professional_entity_sources (default: cbo)",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset_dir)
    if not dataset_path.is_dir():
        print(f"ERROR: dataset directory not found: {dataset_path}", file=sys.stderr)
        print(
            "Pass --dataset-dir or mount the CBO CSV directory into the container.\n"
            "Expected path (default): migrations/core/seeders/estrutura-cbo",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(run(args.dataset_dir, args.source))


if __name__ == "__main__":
    main()
