"""Extract Jira issue keys from free text for cross-integration linking."""

from __future__ import annotations

import re

_JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")


def extract_jira_issue_keys(*texts: str | None) -> tuple[str, ...]:
    """Return unique Jira keys (e.g. ENG-123) found in any of the given strings."""
    seen: list[str] = []
    for text in texts:
        if not text:
            continue
        for match in _JIRA_KEY_RE.findall(text.upper()):
            if match not in seen:
                seen.append(match)
    return tuple(seen)
