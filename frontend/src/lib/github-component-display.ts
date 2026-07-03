/** Readable labels for auto-provisioned GitHub components. */

export interface GitHubComponentDisplay {
  repo: string;
  folder: string;
  inline: string;
}

const AUTO_GITHUB = /^AUTO:github:([^:]+):(.+)$/;

function repoSlug(repoLabel: string): string {
  const cleaned = repoLabel.trim().replace(/\/+$/, "");
  const slash = cleaned.lastIndexOf("/");
  return slash >= 0 ? cleaned.slice(slash + 1) : cleaned;
}

const MONOREPO_CONTAINER_DIRS = new Set([
  "services",
  "packages",
  "apps",
  "libs",
  "modules",
  "components",
]);

function displayFolder(pathPrefix: string): string {
  const parts = pathPrefix
    .trim()
    .replace(/^\/+|\/+$/g, "")
    .split("/")
    .filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length >= 3 && parts[0] === "docs" && parts[1] === "features") {
    return parts[2] ?? "";
  }
  if (parts.length >= 2 && MONOREPO_CONTAINER_DIRS.has(parts[0] ?? "")) {
    return `${parts[0]}/${parts[1]}`;
  }
  return parts[0] ?? "";
}

function buildDisplay(repoLabel: string, pathPrefix: string): GitHubComponentDisplay {
  const repo = repoSlug(repoLabel);
  const folder = displayFolder(pathPrefix);
  return {
    repo,
    folder,
    inline: folder ? `${repo} / ${folder}` : repo,
  };
}

export function parseGitHubComponentDisplay(
  description?: string | null,
  label?: string,
): GitHubComponentDisplay | null {
  if (description?.startsWith("AUTO:")) {
    const body = description.slice("AUTO:".length);
    const match = body.match(AUTO_GITHUB);
    if (match) {
      return buildDisplay(match[1], match[2]);
    }
  }

  if (label?.includes(" / ")) {
    const [repoPart, suffix] = label.split(" / ", 2);
    if (repoPart && suffix) {
      const slug = suffix
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      if (slug) {
        return buildDisplay(repoPart.trim(), `${slug}/`);
      }
    }
  }

  return null;
}

export function formatKraComponentLabel(component: {
  label: string;
  description?: string | null;
}): string {
  return (
    parseGitHubComponentDisplay(component.description, component.label)?.inline ??
    component.label
  );
}

export function truncateComponentLabel(label: string, max = 14): string {
  if (label.length <= max) return label;
  return `${label.slice(0, max - 1)}…`;
}
