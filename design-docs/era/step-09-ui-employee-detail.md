# Step 09 — UI Employee Detail

**Depends on:** 08, 03  
**Blocks:** 12, **16**  
**Estimate:** 4–5 days

## Reference-inspired additions

| Feature | Step |
|---------|------|
| “Start exit handover” CTA | 16 |
| Review network mini-graph | 15 |
| File hotspot mini-matrix | 13 |
| Backup candidates with “ramping” label | 10, 15 |

## Goal

Deep drill-down for a single employee: full evidence, dimension breakdown, affected components graph, backup candidates, mitigations, and export — without losing command center context.

## Pattern

**Slide-over drawer** from right (width `max-w-2xl` / 672px) preferred over full page navigation.

Alternative route: `/era?employee={id}` opens drawer on load (shareable URL).

```mermaid
flowchart LR
    CC[Command Center] -->|row click / View profile| DR[Detail Drawer]
    DR -->|Esc / close| CC
    DR -->|Open KRA| KRA[/kra?component=]
    DR -->|Fix identity| SET[/settings identity]
```

## Drawer layout (top → bottom)

### 1. Hero (`EraDetailHero`)

```
┌─────────────────────────────────────────────────┐
│  [FC]  Frank Osei                    ┌──────┐  │
│        Staff Engineer · Payments     │ 82%  │  │
│        emp-frank · 4.2y tenure       │ RISK │  │
│        [HIGH] [Departure watchlist]  └──────┘  │
│                                                 │
│  If Frank leaves, Payments + Auth recovery      │
│  estimated 3–6 weeks.                         │
└─────────────────────────────────────────────────┘
```

| Element | Source |
|---------|--------|
| Initials avatar | `name` |
| Risk ring | `risk_factor_score` animated SVG |
| Badges | `risk_level`, `departure_watchlist` |
| Recovery copy | `recovery_estimate_weeks` |

### 2. Dimension grid (`EraDimensionGrid`)

5 cards in one row (wrap on mobile):

```
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ K  78   │ │ O  34   │ │ D  65   │ │ S  12   │ │ B  55   │
│ Knowl.  │ │ Oper.   │ │ Docs    │ │ Struct. │ │ Burnout │
│ ████░░  │ │ ██░░░░  │ │ ████░   │ │ █░░░░░  │ │ ███░░░  │
│ Primary │ │         │ │ driver  │ │         │ │ watch   │
│ driver  │ │         │ │         │ │         │ │         │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

Highlight card matching highest dimension contribution.

`partial` dimensions: dashed border + "Partial data" tooltip.

### 3. Charts row

- Left: `EraDimensionRadar` (full size)
- Right: weighted bar breakdown (upgrade existing `EraRiskChart` to 5 dimensions)

### 4. Evidence list (`EraEvidenceList`)

Full scrollable list from `GET /api/analytics/era/{id}`.

**`EraEvidenceCard` (full variant):**

```
┌────────────────────────────────────────────────────────┐
│ 🔴 HIGH · Knowledge                           24 pts   │
│ Sole contributor on Payments Gateway (78% commits)     │
│ No backup reviewer on last 12 PRs.                     │
│                                                        │
│ [GitHub PR #441] [GitHub PR #438] [CODEOWNERS]         │
│ [View in KRA]  [Mark mitigated ▼]                      │
└────────────────────────────────────────────────────────┘
```

- Expand/collapse long descriptions
- Source chips open external URLs in new tab
- `synthetic: true` → amber "Estimated" badge

### 5. Affected components (`EraAffectedComponentsGraph`)

Embed trimmed KRA subgraph:

- Center: employee node
- Nodes: `affected_components`
- SPOF components: red ring
- Click component → `/kra?highlight={id}`

Reuse KRA link rendering logic; subset max 8 components.

### 6. Backup candidates (`EraBackupCandidates`)

Placeholder until Step 10; then:

```
Recommended backups for Payments:
1. Alice Chen — 22% ownership, 8 reviews (ramping)
2. Ben Rivera — 15% ownership, 3 reviews
```

Empty state: "No backup candidates identified — schedule pairing"

### 7. Mitigations (`EraMitigationChecklist`)

From Step 12 rules — checklist UI with status toggles.

### 8. Footer (`EraDetailFooter`)

```
Identity: GitHub ✓  Jira ✓  Slack ✓  Notion ✓
Last sync: GitHub 2h · Jira 2h · Slack 6h · Notion 1d
Data completeness: 92%
[Export PDF] [Copy link]
```

## Interactions

| Action | Behavior |
|--------|----------|
| Open drawer | Slide in 200ms, focus trap |
| Esc | Close drawer |
| URL `?employee=id` | Deep link on page load |
| Export PDF | Print-friendly CSS `@media print` |
| Mark mitigated | `PATCH` evidence mitigation_status (Step 12) |

## Edge cases

| Case | UI |
|------|-----|
| 0 evidence | "Low observable risk — connect more integrations" |
| `excluded` leadership | Drawer shows "Not applicable for ERA" + link to team roll-up |
| `demo_mode` | Banner in drawer |
| Very long evidence list | Virtualized list >20 items |
| Missing URLs | Chip without link, copy label only |
| Employee not found | 404 toast, close drawer |

## API

```
GET /api/analytics/era/{employee_id}
→ full evidence[], all affected_components, backup_candidates[]
```

## Testing

- [ ] Drawer opens/closes without layout shift
- [ ] Deep link `?employee=` works
- [ ] Print export readable
- [ ] External links have `rel="noopener"`

## Exit criteria

- [ ] Full evidence visible with source links
- [ ] KRA cross-link from component graph
- [ ] Dimension grid matches API `dimensions`

## Files to create

```
frontend/src/components/era/
  EraDetailDrawer.tsx
  EraDetailHero.tsx
  EraDimensionGrid.tsx
  EraEvidenceList.tsx
  EraAffectedComponentsGraph.tsx
  EraBackupCandidates.tsx
  EraDetailFooter.tsx
```
