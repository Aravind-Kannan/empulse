# Identity Mapping

**Route:** `/settings/identity-mapping`  
**Audience:** Tenant admins, engineering managers

Canonical **employee ↔ provider user** registry. Every telemetry event passes through `resolve_employee()` — confirmed mapping, email match, or quarantine. No silent mis-attribution.

## Capabilities

- Reconciliation grid (employees × GitHub / Jira / Slack / Notion)
- Auto-guess by email and name (UI hints only until saved)
- Identity sync (`POST /api/identity/sync`) — pull provider directories, auto-map by email
- Unmapped activity queue and reconcile (`POST /api/identity/reconcile-unmapped`)

## Mapped source paths

- `backend/app/services/identity_resolver.py`
- `backend/app/services/identity_mapping.py`
- `backend/app/services/identity_sync.py`
- `backend/app/services/identity_auto_map.py`
- `backend/app/services/github_identity.py`
- `backend/app/services/provider_members.py`
- `backend/app/services/unmapped_activity.py`
- `backend/app/routes/identity.py`
- `backend/app/schemas/identity.py`
- `backend/tests/test_identity_resolver.py`
- `backend/tests/test_identity_sync.py`
- `backend/tests/test_unmapped_reconcile.py`
- `backend/tests/test_github_identity.py`
- `frontend/src/components/identity-mapping/`
- `frontend/src/app/settings/identity-mapping/`
- `design-docs/era/step-01-identity-foundation.md`

## Provider id formats

| Provider | Stored `provider_username_or_id` | Notes |
|----------|-------------------------------|--------|
| GitHub | `gh-{login}` | Matches PR/blame ingest |
| Jira | `accountId` | Not display name or email |
| Slack | `U…` workspace user id | |
| Notion | Notion user id from directory | |

**Save mappings** after editing. Auto-map during sync does not clear stale quarantine until reconcile runs.

## Related

- [Integration Sync](../integration-sync/README.md) — populates provider member lists
- [ERA](../era/README.md) — consumes resolved attribution for scoring
