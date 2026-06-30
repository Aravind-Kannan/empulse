#!/usr/bin/env python3
"""CLI runner for the Notion -> Cognee end-to-end simulation pipeline."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.config import setup_cognee
from app.services.notion_simulation import run_notion_simulation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Acme Notion -> Cognee simulation pipeline",
    )
    parser.add_argument(
        "--notion-token",
        default=os.getenv("NOTION_INTEGRATION_TOKEN", ""),
        help="Notion internal integration token",
    )
    parser.add_argument(
        "--notion-database-id",
        default=os.getenv("NOTION_DATABASE_ID", ""),
        help="Target Notion database ID",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.getenv("OLLAMA_SIMULATION_MODEL", "llama3.2"),
        help="Ollama model for document generation",
    )
    args = parser.parse_args()

    setup_cognee()

    def log(message: str, status: str = "info") -> None:
        prefix = {"info": "•", "running": "→", "success": "✓", "error": "✗"}.get(status, "•")
        print(f"{prefix} {message}")

    async def _run() -> dict:
        return await run_notion_simulation(
            notion_token=args.notion_token,
            notion_database_id=args.notion_database_id,
            ollama_model=args.ollama_model,
            log=log,
        )

    result = asyncio.run(_run())
    print("\n--- Graph Summary ---")
    print(f"Dataset: {result.get('cognee_dataset')}")
    print(f"Nodes: {len(result.get('nodes', []))}")
    print(f"Edges: {len(result.get('edges', []))}")
    for edge in result.get("edges", [])[:12]:
        print(
            f"  {edge['source']} -[{edge['relationship']}]-> {edge['target']}"
        )
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
