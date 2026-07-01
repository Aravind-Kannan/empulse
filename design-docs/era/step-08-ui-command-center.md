# Step 08 — UI Command Center

**Depends on:** 03 (API v2 schema; mock data acceptable initially)  
**Blocks:** 09, 17  
**Estimate:** 6–8 days

## Reference-inspired UI additions

| Component | Step | Source |
|-----------|------|--------|
| `EraAlertsBanner` | 17 | CodePulse alerts |
| Org health KPI card | 18 | ContributorIQ org health |
| Critical hotspot count KPI | 13 | CodePulse matrix |
| Review cadence banner | 17 | WorkFera risk review |

## Goal

Replace the table-only `EraDashboard` with an **ERA Command Center** where managers grasp full team risk posture in one glance — top risks, drivers, affected systems, data health, and live evidence — without clicking through every employee.

## Design principles

1. **Scan in 3 seconds** — KPI strip + heatmap answer "how bad?"
2. **Explain in 10 seconds** — selected row + evidence feed answer "why?"
3. **Trust** — data health, sync freshness, unmapped banner always visible
4. **No surveillance vibe** — continuity risk framing, not performance ranking
5. **Density with clarity** — cockpit aesthetic; dark zinc/slate palette (existing design system)

## Page route

`/era` — replace content of `EraDashboard` with `EraCommandCenter` shell.

## Desktop layout (≥1280px)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ERA Command Center          [Last sync: 2m ✓] [⚠ 3 unmapped] [Export] [Refresh]  │
│ If top 3 at-risk employees left today → est. recovery 4–9 weeks                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐  │
│ │Team    │ │ High   │ │ SPOF   │ │ Open   │ │Undoc.  │ │ Data health      │  │
│ │Risk 58%│ │ 3      │ │ 2      │ │ P1: 7  │ │ inc: 5 │ │ ████████░░ 82%   │  │
│ │ ▲ +4   │ │ people │ │ comps  │ │        │ │        │ │ 4/4 integrations │  │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └──────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ RISK HEATMAP                                                    [Filters ▼]    │
│ Employee          K    O    D    S    B   │ Risk                                              │
│ ─────────────────────────────────────────────────────────────────────────────  │
│ Frank Osei        ██░  ██░  ███  █░░  ██░ │ 82% ████████████████████░░  HIGH              │
│ Alice Chen        ██░  ███  ██░  █░░  █░░ │ 58% ████████████░░░░░░░░  MED                  │
│ Ben Rivera        █░░  █░░  ███  ███  ██░ │ 45% █████████░░░░░░░░░░  MED                  │
├───────────────────────────────┬──────────────────────────────────────────────────┤
│ TOP RISK PREVIEW              │ TEAM COMPOSITION                                 │
│ (selected / #1 highest)       │ [Donut: team risk by dimension K/O/D/S/B]        │
│                               │ [Sparkline: avg risk 30d — Step 11]              │
│ Frank Osei · 82%              │                                                  │
│ [Radar chart K/O/D/S/B]       │ AFFECTED SYSTEMS                                 │
│                               │ ● Payments (SPOF)  ● Auth                        │
│ Top 3 evidence cards          │ [→ Open KRA]                                     │
│ [View full profile →]         │ IDENTITY GAPS · Fix mappings →                   │
├───────────────────────────────┴──────────────────────────────────────────────────┤
│ CRITICAL EVIDENCE FEED (team-wide)                                               │
│ 🔴 Frank — 78% ownership Payments — GitHub · 2h ago                              │
│ 🟠 PROJ-441 unassigned P1 on Auth — Jira · 1d ago                                │
│ 🟠 Auth runbook stale 200d — Notion — affects Alice                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Component tree

```
EraCommandCenter.tsx
├── EraCommandHeader.tsx
├── EraKpiStrip.tsx
├── EraRiskHeatmap.tsx
│   └── EraDimensionBar.tsx (×5 per row)
├── EraEmployeePreview.tsx
│   ├── EraDimensionRadar.tsx
│   └── EraEvidenceCard.tsx (compact ×3)
├── EraTeamComposition.tsx
│   ├── EraDimensionDonut.tsx
│   ├── EraRiskSparkline.tsx (placeholder until Step 11)
│   └── EraAffectedSystemsChips.tsx
└── EraEvidenceFeed.tsx
```

## Component specifications

### `EraCommandHeader`

| Element | Data source | Behavior |
|---------|-------------|----------|
| Title | static | "ERA Command Center" |
| Subtitle | `team_summary.estimated_recovery_weeks` | Dynamic sentence |
| Sync pill | `sync_freshness` | Green <1h, amber <24h, red stale |
| Unmapped badge | `unmapped_activity` sum | Click → Settings identity |
| Export | client CSV | employee table export |
| Refresh | re-fetch API | Spinner on button |

**Demo mode:** amber left border on entire page + tooltip "Demo data — connect integrations"

### `EraKpiStrip` — 6 cards

| Card | Field | Visual |
|------|-------|--------|
| Team Risk | `avg_risk_score` | Large numeral + `trend_7d` chip if available |
| High Risk | `high_risk_count` | Red accent if > 0 |
| SPOF | `spof_component_count` | Link to `/kra?filter=spof` |
| Open P1 | `open_p1_count` | |
| Undocumented | `undocumented_incident_count` | |
| Data Health | `data_health_pct` | Progress bar + "N/4 integrations" |

### `EraRiskHeatmap` (hero)

**Columns:** Employee (name + role) | K | O | D | S | B | Risk bar + badge

**`EraDimensionBar`:** 0–100 horizontal micro-bar, color by dimension:

| Dimension | Color token |
|-----------|-------------|
| K | `violet-400` |
| O | `orange-400` |
| D | `sky-400` |
| S | `fuchsia-400` |
| B | `rose-400` |

**Risk bar:** gradient emerald → amber → red by composite score.

**Interactions:**

- Row click → select employee (updates preview + highlights feed items)
- Double-click / Enter → open detail drawer (Step 09)
- Keyboard ↑↓ navigate rows

**Sort modes:** highest risk (default), K, O, D, S, B, ownership

**Filters:**

- Risk level: all | high | medium | low
- Team dropdown (from `employee.team_name`)
- "Incomplete identity only"
- "Departure watchlist" (`departure_watchlist === true`)

**Virtualization:** `react-window` when `employees.length > 50`

### `EraEmployeePreview`

Shows `selectedId` or highest-risk employee if none selected.

- Risk ring SVG (82% animated stroke)
- 5-axis radar (`EraDimensionRadar`)
- Top 3 `EraEvidenceCard` compact variant
- CTA: "View full profile" → opens Step 09 drawer

### `EraTeamComposition`

- Donut chart: sum of dimension scores across team (where is pain concentrated?)
- `top_risk_driver` callout text
- Affected systems chips from union of `affected_components` where `spof`
- Identity gaps list (employees with `data_completeness_pct < 80`)

### `EraEvidenceFeed`

- Merges top evidence across team (`team_evidence_feed` from API or client-side sort)
- Filter chips by dimension
- Each row: severity icon, title, employee name, provider icon, relative time
- Click → select employee + scroll preview

## Visual tokens (`era-colors.ts`)

```typescript
export const ERA_DIMENSION_COLORS = {
  knowledge: { bar: "bg-violet-400", text: "text-violet-300", label: "Knowledge" },
  operational: { bar: "bg-orange-400", text: "text-orange-300", label: "Operational" },
  documentation: { bar: "bg-sky-400", text: "text-sky-300", label: "Documentation" },
  structural: { bar: "bg-fuchsia-400", text: "text-fuchsia-300", label: "Structural" },
  burnout: { bar: "bg-rose-400", text: "text-rose-300", label: "Burnout" },
} as const;
```

## Responsive behavior

| Breakpoint | Layout |
|------------|--------|
| ≥1280px | Full layout as wireframe |
| 768–1279px | KPI strip scrolls horizontal; heatmap full width; preview + composition stack |
| <768px | KPI cards carousel; heatmap → card list per employee; feed accordion |

## States

| State | UI |
|-------|-----|
| Loading | Skeleton KPI + 8 skeleton rows |
| Error | Existing retry pattern from `EraDashboard` |
| Empty employees | CTA: "Import org chart" → onboarding |
| `warnings[]` | Toast or inline banner per warning |
| `demo_mode` | Amber page border + KPI tooltip |

## Accessibility

- Heatmap rows: `role="button"`, `aria-selected`
- Risk colors never sole indicator — always show numeric %
- WCAG AA contrast on badges
- `prefers-reduced-motion`: disable ring animation

## Edge cases

| Case | UI |
|------|-----|
| 1 employee | Heatmap single row; hide team composition donut |
| All low risk | Positive empty state "No high continuity risks detected" |
| All high risk | Header subtitle escalates copy |
| Partial dimensions | Dashed dimension bars + tooltip "GitHub not connected" |
| Leadership excluded | Footnote: "Directors excluded from ERA" |
| Long names | Truncate with tooltip |
| 100+ employees | Virtualized heatmap; default filter high risk |

## API integration

```typescript
// fetchEraMetrics() — existing, extended types
const data = await fetchEraMetrics();
// data.team_summary, data.employees[].dimensions, etc.
```

## Migration from current UI

1. Build `EraCommandCenter` alongside `EraDashboard`
2. Feature flag `ERA_COMMAND_CENTER=true` in env or workspace settings
3. Swap `era/page.tsx` import when stable
4. Deprecate old table-only layout

## Testing

- [ ] Visual regression: 1440×900 screenshot baseline
- [ ] Lighthouse a11y ≥ 90 on `/era`
- [ ] 100-row virtualization smooth scroll
- [ ] Demo mode banner visible with Acme fallback

## Exit criteria

- [ ] All `team_summary` KPIs visible without scrolling on 1440×900
- [ ] User identifies top 3 risks + top driver in <5s (manual test)
- [ ] Evidence feed populated from API
- [ ] Cross-link to KRA works for SPOF chips

## Files to create

```
frontend/src/components/era/
  EraCommandCenter.tsx
  EraCommandHeader.tsx
  EraKpiStrip.tsx
  EraRiskHeatmap.tsx
  EraDimensionBar.tsx
  EraDimensionRadar.tsx
  EraEmployeePreview.tsx
  EraEvidenceCard.tsx
  EraTeamComposition.tsx
  EraDimensionDonut.tsx
  EraEvidenceFeed.tsx
  era-colors.ts
```

## References (UI patterns)

- [CodePulse Knowledge Silo matrix](https://codepulsehq.com/features/knowledge-silos) — ownership × risk grid
- [ContributorIQ heatmaps](https://contributoriq.com/use-cases/departure-risk) — contributor concentration stripes
- Jellyfish executive KPI strips — team rollup before drill-down
- PagerDuty incident feed — urgency-ordered event stream
