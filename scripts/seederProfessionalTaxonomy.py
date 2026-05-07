"""Seeder for the professional taxonomy tables using the ESCO v1.2.1 dataset.

Usage:
    python scripts/seederProfessionalTaxonomy.py
    python scripts/seederProfessionalTaxonomy.py --dataset-dir /path/to/csvs
    python scripts/seederProfessionalTaxonomy.py --no-reset  # skip delete phase
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

_DEFAULT_DATASET_DIR = str(
    _ROOT / "migrations" / "core" / "seeders" / "ESCO_dataset-v1.2.1-classification-pt-csv"
)

from scaffold.db.session import close_engine, get_session_factory  # noqa: E402
from scaffold.professional.esco_importer import EscoImporter  # noqa: E402


async def run(dataset_dir: str, source: str, reset: bool) -> None:
    factory = get_session_factory()
    async with factory() as session:
        importer = EscoImporter(session, Path(dataset_dir), source=source)
        stats = await importer.run(reset=reset)

    print("\n=== ESCO Import Summary ===")
    for key, count in stats.items():
        print(f"  {key:30s}: {count:>8,}")
    print("===========================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed professional taxonomy from ESCO dataset")
    parser.add_argument(
        "--dataset-dir",
        default=_DEFAULT_DATASET_DIR,
        dest="dataset_dir",
        help="Path to ESCO CSV directory",
    )
    parser.add_argument(
        "--source",
        default="esco",
        help="Source label written to professional_entity_sources (default: esco)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        dest="no_reset",
        help="Skip deletion of existing data before import",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.dataset_dir, args.source, reset=not args.no_reset))
    finally:
        asyncio.run(close_engine())


if __name__ == "__main__":
    main()
