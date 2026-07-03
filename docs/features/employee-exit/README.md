# Employee Exit (EE)

**Route:** `/exit`  
**Audience:** Engineering managers, HR business partners

Generates a structured **handover pack** (markdown) when someone departs — critical knowledge, owned components, open work, tacit gaps, and suggested successors. Can be pre-filled from ERA.

## Capabilities

- Employee picker (non-leadership roles)
- ERA pre-fill via `/exit?employee={id}&prefill=era`
- Downloadable handover markdown
- Pulls ERA evidence, components, mitigations, hotspots, Jira backlog

## Mapped source paths

- `backend/app/services/exit_handover.py`
- `backend/app/routes/exit.py`
- `backend/app/schemas/exit.py`
- `backend/tests/test_exit_handover_era.py`
- `frontend/src/components/exit/`
- `frontend/src/app/exit/`
- `frontend/src/components/landing/BentoExitHandover.tsx`
- `design-docs/era/step-16-era-exit-bridge.md`
- `notion-docs/design/04-employee-exit.md`

## Identity & sync notes

Exit handover reads **already-attributed** ERA data. Ensure:

1. [Identity Mapping](../identity-mapping/README.md) is complete for GitHub/Jira/Slack/Notion
2. [Integration sync](../integration-sync/README.md) has run so ownership and evidence reflect current contributors

## Related

- [ERA](../era/README.md) — risk scores and evidence source
- [ERA exit bridge spec](../../design-docs/era/step-16-era-exit-bridge.md)
