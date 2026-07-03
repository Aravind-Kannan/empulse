# Employee Exit (EE)

**Route:** `/exit`  
**Audience:** Engineering managers, HR business partners  
**Abbreviation:** EE

> **ERA bridge spec:** Repo `design-docs/era/step-16-era-exit-bridge.md`

---

## Purpose

Generate a structured **handover pack** (markdown) when an employee departs — capturing critical knowledge, owned components, open work, tacit gaps, and suggested successors.

**Core question:**

> What must transfer before this person leaves so the team can operate?

---

## User flow

```
1. Select employee from dropdown (non-leadership roles)
2. Optional: arrive from ERA detail → "Start exit handover" (pre-fill)
3. Preview handover sections
4. Download markdown file
```

### ERA pre-fill path

| Trigger | URL |
|---------|-----|
| ERA detail drawer | `/exit?employee={id}&prefill=era` |
| API | `GET /api/exit/handover?id={employee_id}&prefill=era=true` |

Banner on Exit page when opened from ERA: *"Pre-filled from ERA risk assessment"*

---

## Handover sections

| Section | Source |
|---------|--------|
| Critical knowledge to transfer | Top ERA evidence by impact |
| Owned components & SPOF flags | `affected_components` |
| Suggested successor | Backup candidates (#1 from graph) |
| Open mitigations | ERA mitigations with `status=open` |
| Tacit knowledge gaps | Documentation dimension — undocumented incidents |
| Hotspot files | File risk matrix critical quadrant |
| Jira / ops backlog | Operational dimension counts + links |
| Undocumented hotfixes | Cognee graph traversal flags |

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/exit/employees` | Exit-eligible employees (excludes leadership) |
| `GET` | `/api/exit/handover` | Markdown handover; `?id=` required; `?prefill=era=true` optional |

### Response shape

```json
{
  "markdown": "# Handover: ...",
  "filename": "handover-alice-smith.md",
  "era_risk_score": 72.5,
  "era_sections_included": ["evidence", "components", "successor"]
}
```

---

## Edge cases

| Case | Handling |
|------|----------|
| ERA data stale | Show `computed_at` in handover header |
| `demo_mode` | Warn in preamble |
| Leadership employee | ERA excluded; generic handover still works |
| No ERA evidence | Fallback template sections |

---

## Cross-module links

| Module | Link |
|--------|------|
| ERA | Pre-fill evidence, risk score, mitigations |
| KRA | SPOF flags on owned components |
| II | Undocumented incident references |

---

## Success criteria

- [ ] Handover includes ERA sections when `prefill=era`
- [ ] One-click ERA detail → Exit navigation
- [ ] Open mitigations copied as checklist in markdown
- [ ] Leadership correctly excluded from ERA-enriched sections

---

## Related

- [ERA design](./01-era.md)
- [Runbook: ERA review cadence](../runbooks/06-era-review-cadence.md)
