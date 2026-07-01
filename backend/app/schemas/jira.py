from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

JIRA_DOMAIN_RE = re.compile(
    r"^https?://[a-zA-Z0-9][-a-zA-Z0-9]*\.atlassian\.net/?$",
    re.IGNORECASE,
)
PROJECT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")


def normalize_jira_domain(raw: str) -> str:
    cleaned = raw.strip().rstrip("/")
    if not cleaned.startswith("http"):
        cleaned = f"https://{cleaned}"
    if not cleaned.endswith(".atlassian.net"):
        if ".atlassian.net" not in cleaned:
            raise ValueError(
                "Jira site must be an Atlassian Cloud URL, e.g. https://acme.atlassian.net"
            )
    if not JIRA_DOMAIN_RE.match(cleaned):
        raise ValueError(
            "Jira site must be an Atlassian Cloud URL, e.g. https://acme.atlassian.net"
        )
    return cleaned.rstrip("/")


def parse_project_keys(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    keys: list[str] = []
    for part in raw.split(","):
        key = part.strip().upper()
        if not key:
            continue
        if not PROJECT_KEY_RE.match(key):
            raise ValueError(
                f"Invalid project key '{part.strip()}'. "
                "Use comma-separated keys like ENG, PLAT (1–10 uppercase letters/digits)."
            )
        if key not in keys:
            keys.append(key)
    return keys


class JiraConnectRequest(BaseModel):
    jira_domain: str = Field(min_length=1, description="Atlassian Cloud site URL")
    auth_email: EmailStr
    api_token: str = Field(min_length=1, description="Atlassian API token (stored encrypted)")
    project_keys: str = Field(
        default="",
        description="Comma-separated project keys; empty imports all projects",
    )

    @field_validator("jira_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return normalize_jira_domain(value)

    @field_validator("api_token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Jira API token is required.")
        return cleaned

    @field_validator("project_keys")
    @classmethod
    def validate_project_keys(cls, value: str) -> str:
        keys = parse_project_keys(value)
        return ", ".join(keys)


class JiraValidateRequest(BaseModel):
    jira_domain: str = Field(min_length=1)
    auth_email: EmailStr
    api_token: str = Field(min_length=1)

    @field_validator("jira_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return normalize_jira_domain(value)

    @field_validator("api_token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Jira API token is required.")
        return cleaned


class JiraValidateResponse(BaseModel):
    valid: bool
    message: str
    account_display_name: str | None = None


class JiraDebugStage(BaseModel):
    name: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    detail: str | None = None


class JiraDebugState(BaseModel):
    tenant_id: str
    status: str
    stages: list[JiraDebugStage]
    issues_fetched: int = 0
    documents_appended: int = 0
    last_error: str | None = None
    updated_at: str


class JiraIntegrationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    jira_domain: str
    auth_email: str
    project_keys: str
    project_scope: Literal["all", "specific"]
    status: str
    last_synced_at: datetime | None
    issues_synced_count: int
    api_token_configured: bool = True
    api_token_preview: str = "••••••••"
