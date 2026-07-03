# Onboarding & Auth

**Routes:** `/`, `/onboarding`  
**Audience:** New tenants, platform admins

---

## Auth flow

```
/ (landing)
  ├── Sign Up → /onboarding (3-step wizard)
  └── Login   → /dashboard

Authenticated routes protected by AuthGuard
AppShell hides sidebar on / and /onboarding
```

### Session storage

| Key | Store | Contents |
|-----|-------|----------|
| `empulse-auth-session` | localStorage | Mock auth session (user, tenant) |
| `empulse-integrations-config` | localStorage | Integration UI state |
| Onboarding step | OnboardingContext | Wizard progress |

---

## Onboarding wizard (3 steps)

| Step | Focus | Delivers |
|------|-------|----------|
| 1 | Org chart | Employee + component structure |
| 2 | Integrations | Connect GitHub, Jira, Notion, Slack |
| 3 | Review & launch | Confirm, trigger initial sync |

### Org chart ingest

```
POST /api/ingest/org-chart
        │
        ▼
cognee_ingest.py → Cognee graph (GraphEmployee, GraphComponent)
        │
        ▼
PostgreSQL employees, components, assignments
```

Tenant bootstrap also seeds:

- Demo incidents (II)
- Default integration config stubs

---

## Tenant bootstrap

On first tenant creation:

| Artifact | Action |
|----------|--------|
| `Tenant` row | Created with UUID |
| Cognee dataset | `empulse_tenant_{uuid}` |
| Demo incidents | 5 records across 3 system scopes |
| Employees | From org chart ingest or Notion import |

Default bootstrap tenant UUID (dev): `00000000-0000-4000-8000-000000000001`

---

## Identity reconciliation (post-onboarding)

After connectors sync, unmapped activity appears in ERA unmapped banner.

**Action:** Settings → Identity mappings → confirm provider ↔ employee links.

Until confirmed, telemetry for that provider user stays quarantined.

---

## Prerequisites for full platform value

| Milestone | Unlocks |
|-----------|---------|
| Org chart ingested | ERA structural dimension, KRA graph |
| GitHub connected + synced | DOA, file risk, bus factor |
| Jira connected | II workspace, operational load |
| Notion connected | Doc coverage, directory enrichment |
| Identity map complete | Accurate per-person ERA scores |

---

## UI providers

Global React context (see `components/Providers.tsx`):

- `AuthContext`
- `WorkspaceContext`
- `IntegrationsContext`
- `OnboardingContext`

---

## Related

- [Platform overview](./00-platform-overview.md)
- [Dashboard setup checklist](./05-dashboard.md)
- [Integrations](./06-integrations-platform.md)
- [Runbook: local development](../runbooks/01-local-development.md)
