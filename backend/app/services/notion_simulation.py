from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.config import get_settings, run_cognee_add_and_cognify

NOTION_VERSION = "2022-06-28"
SIMULATION_DATASET = "empulse_notion_simulation"
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
MOCK_NOTION_DIR = BACKEND_ROOT / ".data_storage" / "notion_sim"

ENGINEERS = [
    "Lisa Wang",
    "Mike Chen",
    "Alice Chen",
    "Ben Rivera",
    "Cara Patel",
    "Diego Alvarez",
]

SYSTEMS = [
    "Payment Gateway",
    "Auth Service",
    "Notification Hub",
    "Redis Cache",
]

FALLBACK_DOCUMENTS = [
    {
        "title": "Payment Gateway Architecture & Failure Modes",
        "doc_type": "architecture",
        "author": "Lisa Wang",
        "content": """# Payment Gateway Architecture & Failure Modes

Author: Lisa Wang
Reviewers: Mike Chen, Ben Rivera
Component: Payment Gateway

## Overview
The Payment Gateway orchestrates checkout, refunds, and provider webhooks for Acme Company.
Lisa Wang owns the primary architecture review and documents failure modes for on-call rotation.

## Failure Modes
- Stripe webhook delay impacts Payment Gateway settlement latency.
- Mike Chen noted that Auth Service token validation failures cascade into checkout errors.
- Redis Cache saturation during flash sales can block Payment Gateway session lookups.

## Dependencies
Payment Gateway -> Auth Service -> Redis Cache
Ben Rivera maintains refund reconciliation playbooks linked to this architecture.""",
    },
    {
        "title": "Postmortem: Auth Service Redis Cache Outage",
        "doc_type": "postmortem",
        "author": "Mike Chen",
        "content": """# Postmortem: Auth Service Redis Cache Outage

Incident Commander: Mike Chen
Authors: Lisa Wang, Cara Patel
Impacted Systems: Auth Service, Redis Cache, Payment Gateway

## Summary
On 2026-06-12, Auth Service Redis Cache eviction caused widespread session invalidation.
Mike Chen authored this postmortem. Lisa Wang validated customer impact on Payment Gateway.

## Timeline
- 09:14 UTC: Redis Cache memory pressure alerts fire for Auth Service cluster.
- 09:27 UTC: Payment Gateway checkout failures spike due to Auth Service dependency.
- 10:05 UTC: Cara Patel restores Redis Cache capacity and rolls Auth Service pods.

## Action Items
- Mike Chen -> IMPACTS -> Auth Service
- Auth Service outage -> IMPACTS -> Payment Gateway
- Lisa Wang to update architecture review with new Redis Cache guardrails.""",
    },
    {
        "title": "Acme Engineering Rotation & Component Ownership Wiki",
        "doc_type": "handover",
        "author": "Alice Chen",
        "content": """# Acme Engineering Rotation & Component Ownership Wiki

Maintainer: Alice Chen
Last Updated By: Diego Alvarez

## Component Owners
- Payment Gateway: Lisa Wang (primary), Ben Rivera (backup)
- Auth Service: Mike Chen (primary), Cara Patel (backup)
- Notification Hub: Diego Alvarez (primary), Elena Kowalski (backup)
- Redis Cache: Cara Patel (primary), Mike Chen (backup)

## Rotation Notes
Alice Chen manages quarterly handover for Acme Company engineering teams.
Lisa Wang documents Payment Gateway runbooks in Notion.
Mike Chen links Auth Service postmortems to the on-call wiki.
Diego Alvarez owns Notification Hub webhook escalation paths.""",
    },
]


@dataclass
class GeneratedDocument:
    title: str
    doc_type: str
    author: str
    content: str
    notion_page_id: str | None = None


LogCallback = Callable[[str, str], None]


def _chunk_text(text: str, size: int = 1800) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [text[:size]]


def generate_documents_with_ollama(
    model: str,
    endpoint: str = "http://localhost:11434",
) -> list[GeneratedDocument]:
    documents: list[GeneratedDocument] = []
    prompts = [
        (
            "architecture",
            "Payment Gateway Architecture & Failure Modes",
            "Lisa Wang",
            "Write a detailed architecture design review for Acme Company's Payment Gateway. "
            "Explicitly mention engineers Lisa Wang, Mike Chen, Ben Rivera and systems "
            "Payment Gateway, Auth Service, Redis Cache with dependency arrows.",
        ),
        (
            "postmortem",
            "Postmortem: Auth Service Redis Cache Outage",
            "Mike Chen",
            "Write an incident postmortem where Mike Chen and Lisa Wang respond to an "
            "Auth Service Redis Cache outage that impacts Payment Gateway.",
        ),
        (
            "handover",
            "Acme Engineering Rotation & Component Ownership Wiki",
            "Alice Chen",
            "Write a team rotation wiki listing component owners for Payment Gateway, "
            "Auth Service, Notification Hub, and Redis Cache. Mention Alice Chen, "
            "Diego Alvarez, Lisa Wang, and Mike Chen.",
        ),
    ]

    for doc_type, title, author, prompt in prompts:
        try:
            response = requests.post(
                f"{endpoint.rstrip('/')}/api/generate",
                json={
                    "model": model,
                    "prompt": (
                        f"You are an engineering documentation writer for Acme Company.\n"
                        f"Title: {title}\n"
                        f"{prompt}\n"
                        "Return markdown with headings, named engineers, and explicit system links."
                    ),
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            content = response.json().get("response", "").strip()
            if len(content) < 200:
                raise ValueError("Ollama response too short")
            documents.append(
                GeneratedDocument(
                    title=title,
                    doc_type=doc_type,
                    author=author,
                    content=content,
                )
            )
        except Exception:
            fallback = next(doc for doc in FALLBACK_DOCUMENTS if doc["title"] == title)
            documents.append(
                GeneratedDocument(
                    title=fallback["title"],
                    doc_type=fallback["doc_type"],
                    author=fallback["author"],
                    content=fallback["content"],
                )
            )

    return documents


def _notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _paragraph_blocks(content: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for chunk in _chunk_text(content):
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}],
                },
            }
        )
    return blocks


def write_documents_to_notion(
    documents: list[GeneratedDocument],
    *,
    token: str,
    database_id: str,
) -> list[GeneratedDocument]:
    if not token.strip():
        return _write_documents_locally(documents)

    parent: dict[str, Any]
    if database_id.strip():
        parent = {"database_id": database_id.strip()}
        title_property = "Name"
    else:
        search = requests.post(
            "https://api.notion.com/v1/search",
            headers=_notion_headers(token),
            json={"page_size": 1},
            timeout=30,
        )
        search.raise_for_status()
        results = search.json().get("results", [])
        if not results:
            return _write_documents_locally(documents)
        parent = {"page_id": results[0]["id"]}
        title_property = "title"

    written: list[GeneratedDocument] = []
    for document in documents:
        payload = {
            "parent": parent,
            "properties": {
                title_property: {
                    "title": [{"text": {"content": document.title[:200]}}],
                }
            },
            "children": _paragraph_blocks(document.content),
        }
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_notion_headers(token),
            json=payload,
            timeout=60,
        )
        if response.status_code >= 400 and title_property == "Name":
            payload["properties"] = {
                "title": {"title": [{"text": {"content": document.title[:200]}}]}
            }
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=_notion_headers(token),
                json=payload,
                timeout=60,
            )
        response.raise_for_status()
        page_id = response.json()["id"]
        written.append(
            GeneratedDocument(
                title=document.title,
                doc_type=document.doc_type,
                author=document.author,
                content=document.content,
                notion_page_id=page_id,
            )
        )
    return written


def _write_documents_locally(documents: list[GeneratedDocument]) -> list[GeneratedDocument]:
    MOCK_NOTION_DIR.mkdir(parents=True, exist_ok=True)
    written: list[GeneratedDocument] = []
    for document in documents:
        page_id = f"mock-{uuid.uuid4().hex[:12]}"
        path = MOCK_NOTION_DIR / f"{page_id}.json"
        path.write_text(
            json.dumps(
                {
                    "id": page_id,
                    "title": document.title,
                    "doc_type": document.doc_type,
                    "author": document.author,
                    "content": document.content,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        written.append(
            GeneratedDocument(
                title=document.title,
                doc_type=document.doc_type,
                author=document.author,
                content=document.content,
                notion_page_id=page_id,
            )
        )
    return written


def pull_documents_from_notion(
    documents: list[GeneratedDocument],
    *,
    token: str,
) -> list[GeneratedDocument]:
    if not token.strip():
        return documents

    pulled: list[GeneratedDocument] = []
    for document in documents:
        if not document.notion_page_id or document.notion_page_id.startswith("mock-"):
            pulled.append(document)
            continue

        blocks_response = requests.get(
            f"https://api.notion.com/v1/blocks/{document.notion_page_id}/children",
            headers=_notion_headers(token),
            params={"page_size": 100},
            timeout=30,
        )
        blocks_response.raise_for_status()
        text_parts: list[str] = []
        for block in blocks_response.json().get("results", []):
            if block.get("type") != "paragraph":
                continue
            for rich_text in block.get("paragraph", {}).get("rich_text", []):
                text_parts.append(rich_text.get("plain_text", ""))
        content = "\n\n".join(text_parts).strip() or document.content
        pulled.append(
            GeneratedDocument(
                title=document.title,
                doc_type=document.doc_type,
                author=document.author,
                content=content,
                notion_page_id=document.notion_page_id,
            )
        )
    return pulled


def extract_graph_from_documents(documents: list[GeneratedDocument]) -> tuple[list[dict], list[dict]]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(label: str, node_type: str) -> str:
        node_id = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "type": node_type}
        return node_id

    for document in documents:
        doc_id = add_node(document.title, "document")
        author_id = add_node(document.author, "person")
        edges.append(
            {
                "source": author_id,
                "target": doc_id,
                "relationship": "AUTHOR_OF",
            }
        )

        for engineer in ENGINEERS:
            if engineer in document.content:
                engineer_id = add_node(engineer, "person")
                if engineer != document.author:
                    edges.append(
                        {
                            "source": engineer_id,
                            "target": doc_id,
                            "relationship": "REFERENCED_IN",
                        }
                    )

        for system in SYSTEMS:
            if system in document.content:
                system_id = add_node(system, "system")
                edges.append(
                    {
                        "source": doc_id,
                        "target": system_id,
                        "relationship": "DOCUMENTS",
                    }
                )
                if document.doc_type == "postmortem":
                    edges.append(
                        {
                            "source": doc_id,
                            "target": system_id,
                            "relationship": "IMPACTS",
                        }
                    )

        if document.doc_type == "handover":
            for line in document.content.splitlines():
                match = re.search(r"^-\s+([^:]+):\s+([^(]+)", line)
                if not match:
                    continue
                system_name = match.group(1).strip()
                owner_name = match.group(2).strip()
                if system_name and owner_name:
                    system_id = add_node(system_name, "system")
                    owner_id = add_node(owner_name, "person")
                    edges.append(
                        {
                            "source": owner_id,
                            "target": system_id,
                            "relationship": "OWNS",
                        }
                    )

    deduped_edges = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (edge["source"], edge["target"], edge["relationship"])
        if key in seen:
            continue
        seen.add(key)
        deduped_edges.append(edge)

    return list(nodes.values()), deduped_edges


async def ingest_documents_to_cognee(documents: list[GeneratedDocument]) -> str:
    settings = get_settings()
    dataset = SIMULATION_DATASET
    combined_sections = []
    for document in documents:
        combined_sections.append(
            f"# {document.title}\n"
            f"Type: {document.doc_type}\n"
            f"Author: {document.author}\n\n"
            f"{document.content}"
        )
    narrative = "\n\n---\n\n".join(combined_sections)
    await run_cognee_add_and_cognify(
        narrative,
        dataset_name=dataset,
        custom_prompt=(
            "Extract engineers, documents, components, and relationships such as "
            "AUTHOR_OF, IMPACTS, OWNS, and DOCUMENTS from Acme Company Notion pages."
        ),
    )
    return dataset


async def run_notion_simulation(
    *,
    notion_token: str = "",
    notion_database_id: str = "",
    ollama_model: str = "llama3.2",
    log: LogCallback | None = None,
) -> dict[str, Any]:
    def emit(message: str, status: str = "info") -> None:
        if log:
            log(message, status)

    settings = get_settings()
    endpoint = settings.llm_endpoint.replace("/v1", "")

    emit("[Ollama generating data...]", "running")
    documents = await asyncio.to_thread(
        generate_documents_with_ollama,
        ollama_model,
        endpoint,
    )
    emit(f"Generated {len(documents)} engineering documents via Ollama.", "success")

    emit("[Writing to Notion...]", "running")
    written = await asyncio.to_thread(
        write_documents_to_notion,
        documents,
        token=notion_token,
        database_id=notion_database_id,
    )
    mode = "Notion API" if notion_token.strip() else "local mock Notion store"
    emit(f"Wrote {len(written)} pages via {mode}.", "success")

    emit("[Polling Notion content...]", "running")
    pulled = await asyncio.to_thread(
        pull_documents_from_notion,
        written,
        token=notion_token,
    )
    emit(f"Pulled {len(pulled)} documents back for ingestion.", "success")

    emit("[Cognee Extracting Triples...]", "running")
    dataset = await ingest_documents_to_cognee(pulled)
    nodes, edges = extract_graph_from_documents(pulled)
    emit("[Graph Built Successfully!]", "success")

    return {
        "success": True,
        "documents_generated": len(documents),
        "notion_pages_written": len(written),
        "cognee_dataset": dataset,
        "nodes": nodes,
        "edges": edges,
    }


async def stream_notion_simulation(
    *,
    notion_token: str = "",
    notion_database_id: str = "",
    ollama_model: str = "llama3.2",
) -> AsyncIterator[str]:
    queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

    def log(message: str, status: str = "info") -> None:
        queue.put_nowait((message, status))

    async def worker() -> None:
        try:
            result = await run_notion_simulation(
                notion_token=notion_token,
                notion_database_id=notion_database_id,
                ollama_model=ollama_model,
                log=log,
            )
            queue.put_nowait(
                (
                    "__RESULT__",
                    json.dumps({"type": "result", **result}),
                )
            )
        except Exception as exc:
            queue.put_nowait((f"Simulation failed: {exc}", "error"))
            queue.put_nowait(
                (
                    "__RESULT__",
                    json.dumps({"type": "result", "success": False, "nodes": [], "edges": []}),
                )
            )
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(worker())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            message, status = item
            if message == "__RESULT__":
                yield f"data: {status}\n\n"
            else:
                payload = json.dumps(
                    {"type": "log", "message": message, "status": status}
                )
                yield f"data: {payload}\n\n"
    finally:
        await task
