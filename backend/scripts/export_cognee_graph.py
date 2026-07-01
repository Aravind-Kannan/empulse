#!/usr/bin/env python3
"""Export a Cognee knowledge graph to a self-contained HTML file for local viewing."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.config import setup_cognee
from app.services.tenant_cognee import tenant_cognee_context_for_dataset
from app.ssl import configure_ssl
from app.tenancy import tenant_dataset_name

DEFAULT_OUTPUT = BACKEND_ROOT / "exports" / "cognee_graph.html"


def _list_datasets() -> list[str]:
    import sqlite3

    db_path = BACKEND_ROOT / ".cognee_system" / "databases" / "cognee_db"
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT name FROM datasets ORDER BY name").fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def _resolve_dataset_name(args: argparse.Namespace) -> str:
    if args.dataset:
        return args.dataset
    if args.tenant_id:
        return tenant_dataset_name(uuid.UUID(args.tenant_id))
    datasets = _list_datasets()
    tenant_datasets = [name for name in datasets if name.startswith("empulse_tenant_")]
    if tenant_datasets:
        return tenant_datasets[-1]
    if datasets:
        return datasets[-1]
    raise SystemExit(
        "No dataset specified and none found in Cognee. "
        "Pass --dataset or --tenant-id, or run onboarding ingest first."
    )


async def _export_graph(
    dataset: str,
    output_path: Path,
    *,
    include_session_events: bool,
) -> None:
    import cognee

    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with tenant_cognee_context_for_dataset(dataset):
        await cognee.visualize_graph(
            destination_file_path=str(output_path.resolve()),
            dataset=dataset,
            include_session_events=include_session_events,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Cognee graph to an interactive HTML file",
    )
    parser.add_argument(
        "--dataset",
        help="Cognee dataset name (e.g. empulse_tenant_<uuid>)",
    )
    parser.add_argument(
        "--tenant-id",
        help="Tenant UUID; resolves to empulse_tenant_<uuid-without-hyphens>",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path (default: {DEFAULT_OUTPUT.relative_to(BACKEND_ROOT)})",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List dataset names from cognee_db and exit",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the HTML file in the default browser (macOS/Linux)",
    )
    parser.add_argument(
        "--no-session-events",
        action="store_true",
        help="Skip session search/feedback timeline on the Memory tab",
    )
    args = parser.parse_args()

    configure_ssl()
    setup_cognee()

    if args.list_datasets:
        datasets = _list_datasets()
        if not datasets:
            print("No datasets found.", file=sys.stderr)
            return 1
        for name in datasets:
            print(name)
        return 0

    dataset = _resolve_dataset_name(args)
    output_path = args.output if args.output.is_absolute() else BACKEND_ROOT / args.output

    print(f"Dataset: {dataset}")
    print(f"Output:  {output_path.resolve()}")
    print("Tip: ensure Neo4j is running (docker compose up -d neo4j).")

    try:
        asyncio.run(
            _export_graph(
                dataset,
                output_path,
                include_session_events=not args.no_session_events,
            )
        )
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1

    if not output_path.is_file():
        print("Export finished but output file was not created.", file=sys.stderr)
        return 1

    print(f"Wrote {output_path.stat().st_size:,} bytes")
    if args.open:
        subprocess.run(["open", str(output_path.resolve())], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
