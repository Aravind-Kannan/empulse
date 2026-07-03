# Empulse feature map

Feature folders under `docs/features/` serve two purposes:

1. **Component provisioning** — On GitHub integration sync, each feature folder becomes an org-chart **component** (e.g. `Era`, `Integration Sync`).
2. **Path attribution** — Each feature `README.md` lists **mapped source paths**. Those paths are registered in the GitHub `path_component_map` so blame, PRs, and code ingest attribute activity to the right component. Combined with **identity mapping**, contributors resolve to the correct employees in ERA/KRA.

## Features

| Folder | Component | Route |
|--------|-----------|-------|
| [era](./era/README.md) | Era | `/era` |
| [employee-exit](./employee-exit/README.md) | Employee Exit | `/exit` |
| [incident-investigation](./incident-investigation/README.md) | Incident Investigation | `/investigation` |
| [identity-mapping](./identity-mapping/README.md) | Identity Mapping | `/settings/identity-mapping` |
| [integration-sync](./integration-sync/README.md) | Integration Sync | Settings → Integrations |

## How sync uses this

```
GitHub sync
    ├── provision_github_components()  → components from docs/features/*
    ├── parse "Mapped source paths"    → path_component_map entries
    ├── blame / PR / tree ingest       → file path → component_id
    └── identity_resolver              → provider_user_id → employee_id
```

**Identity mapping** (Settings → Identity mapping) must link each GitHub login (`gh-{username}`) to an employee. Without that, activity is quarantined as unmapped — never guessed.

## Related docs

- Design summaries: `notion-docs/design/`
- ERA deep spec: `design-docs/era/`
- Runbook: `notion-docs/runbooks/02-integration-sync.md`
