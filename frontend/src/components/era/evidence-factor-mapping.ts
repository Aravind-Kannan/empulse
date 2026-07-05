import type { EraDimensionKey, EraEvidenceItem } from "@/lib/types";

type FactorKey = string;

interface FactorHint {
  factorKey: FactorKey;
  match: (item: EraEvidenceItem) => boolean;
}

const DIMENSION_HINTS: Record<EraDimensionKey, FactorHint[]> = {
  knowledge: [
    {
      factorKey: "backup_review",
      match: (item) =>
        /no-backup-review|backup reviewer|sole reviewer/i.test(
          `${item.id} ${item.title}`,
        ),
    },
    {
      factorKey: "backup_review",
      match: (item) => /-risky-/i.test(item.id),
    },
    {
      factorKey: "spof",
      match: (item) =>
        /-spof-|sole contributor on/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "ownership",
      match: (item) =>
        /-file-risk-|-doa-max|-decay-|-ownership-|sole-expert|DOA|owns \d+%|Critical file|knowledge decay/i.test(
          `${item.id} ${item.title}`,
        ),
    },
    {
      factorKey: "breadth",
      match: (item) => /breadth|assignment/i.test(`${item.id} ${item.title}`),
    },
  ],
  operational: [
    {
      factorKey: "jira_backlog",
      match: (item) =>
        /unassigned-critical|unassigned critical/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "unresolved_issues",
      match: (item) =>
        /open-p1-p2|high-priority open|unresolved/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "open_tasks",
      match: (item) =>
        /open-prs|open pull request|open task/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "on_call_incidents",
      match: (item) => /oncall|on-call/i.test(`${item.id} ${item.title}`),
    },
  ],
  documentation: [
    {
      factorKey: "components_without_docs",
      match: (item) =>
        /no-runbook|lack.*runbook|without docs/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "stale_runbooks",
      match: (item) =>
        /stale runbook|sole-runbook-author|sole author of.*runbook/i.test(
          `${item.id} ${item.title}`,
        ),
    },
    {
      factorKey: "undocumented_incidents",
      match: (item) =>
        /undocumented|without runbook update|sole responder/i.test(
          `${item.id} ${item.title}`,
        ),
    },
  ],
  structural: [
    {
      factorKey: "incident_escalation_shadow",
      match: (item) => /escalation/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "cross_team_sole_owner",
      match: (item) =>
        /epic-owner|sole owner|cross-team/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "direct_reports",
      match: (item) => /direct report/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "high_risk_roll_up",
      match: (item) => /roll-up|high-risk report/i.test(`${item.id} ${item.title}`),
    },
  ],
  burnout: [
    {
      factorKey: "sprint_points",
      match: (item) => /sprint/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "after_hours_commits",
      match: (item) => /after-hours commit/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "on_call_off_hours_messages",
      match: (item) =>
        /after-hours on-call|off-hours/i.test(`${item.id} ${item.title}`),
    },
    {
      factorKey: "rising_load",
      match: (item) => /rising workload|cycle time/i.test(`${item.id} ${item.title}`),
    },
  ],
};

const FALLBACK_ORDER: Record<EraDimensionKey, FactorKey[]> = {
  knowledge: ["ownership", "spof", "backup_review", "breadth"],
  operational: [
    "unresolved_issues",
    "open_tasks",
    "jira_backlog",
    "on_call_incidents",
  ],
  documentation: [
    "undocumented_incidents",
    "components_without_docs",
    "stale_runbooks",
  ],
  structural: [
    "incident_escalation_shadow",
    "cross_team_sole_owner",
    "direct_reports",
    "high_risk_roll_up",
  ],
  burnout: [
    "sprint_points",
    "after_hours_commits",
    "on_call_off_hours_messages",
    "rising_load",
  ],
};

export function isFactorTemplateEvidence(item: EraEvidenceItem): boolean {
  return (
    /^[^-]+-(knowledge|operational|documentation|structural|burnout)-[a-z_]+-\d+$/.test(
      item.id,
    ) && item.description.includes("impact points (signal value:")
  );
}

function nearestTopFactor(
  dimension: EraDimensionKey,
  factorKey: FactorKey,
  topFactorKeys: string[],
): string | null {
  const order = FALLBACK_ORDER[dimension];
  const index = order.indexOf(factorKey);
  if (index >= 0) {
    for (let cursor = index; cursor < order.length; cursor += 1) {
      if (topFactorKeys.includes(order[cursor])) {
        return order[cursor];
      }
    }
    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      if (topFactorKeys.includes(order[cursor])) {
        return order[cursor];
      }
    }
  }
  return topFactorKeys[0] ?? null;
}

export function resolveEvidenceFactorKey(
  item: EraEvidenceItem,
  dimension: EraDimensionKey,
  topFactorKeys: string[],
): string | null {
  if (item.dimension !== dimension || topFactorKeys.length === 0) {
    return null;
  }
  if (isFactorTemplateEvidence(item)) {
    return null;
  }

  for (const key of topFactorKeys) {
    if (item.id.includes(`-${key}-`)) {
      return key;
    }
  }

  const hints = DIMENSION_HINTS[dimension] ?? [];
  for (const hint of hints) {
    if (!hint.match(item)) {
      continue;
    }
    if (topFactorKeys.includes(hint.factorKey)) {
      return hint.factorKey;
    }
    return nearestTopFactor(dimension, hint.factorKey, topFactorKeys);
  }

  return topFactorKeys[0];
}

export function groupEvidenceByFactor(
  dimension: EraDimensionKey,
  topFactorKeys: string[],
  evidence: EraEvidenceItem[],
): Map<string, EraEvidenceItem[]> {
  const grouped = new Map<string, EraEvidenceItem[]>();
  for (const key of topFactorKeys) {
    grouped.set(key, []);
  }

  for (const item of evidence) {
    const factorKey = resolveEvidenceFactorKey(item, dimension, topFactorKeys);
    if (!factorKey) {
      continue;
    }
    grouped.get(factorKey)?.push(item);
  }

  for (const [key, items] of grouped) {
    grouped.set(
      key,
      items.sort((left, right) => right.impact_points - left.impact_points),
    );
  }

  return grouped;
}
