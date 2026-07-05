import type { IdentityProvider, ProviderMember } from "@/lib/types";

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function integrationUsername(
  member: ProviderMember,
  provider: IdentityProvider,
): string {
  const explicit = member.username?.trim();
  if (explicit) return explicit;

  const id = member.id.trim();
  const label = member.label.trim();

  if (provider === "github") {
    return id.startsWith("gh-") ? id.slice(3) : id;
  }

  if (provider === "slack") {
    if (label.startsWith("@")) return label;
    return id;
  }

  if (provider === "jira") {
    const emailInLabel = label.match(/\(([^)]+@[^)]+)\)/);
    if (emailInLabel?.[1]) return emailInLabel[1];
    if (member.email?.trim()) return member.email.trim();
    return id;
  }

  if (member.email?.trim()) {
    return member.email.trim();
  }

  return id;
}

function integrationDisplayName(
  member: ProviderMember,
  provider: IdentityProvider,
): string {
  let label = member.label.trim();

  if (provider === "jira" && label.includes("(")) {
    label = label.split("(")[0].trim();
  }

  if (provider === "slack" && label.startsWith("@")) {
    return label;
  }

  if (label) return label;

  const username = integrationUsername(member, provider);
  return username || member.id;
}

export function formatProviderMemberOption(
  member: ProviderMember,
  provider: IdentityProvider,
): string {
  const displayName = integrationDisplayName(member, provider);
  const username = integrationUsername(member, provider);

  if (!username) return displayName;
  if (normalize(username) === normalize(displayName)) return displayName;
  if (displayName.toLowerCase().includes(username.toLowerCase())) {
    return displayName;
  }

  return `${displayName} (${username})`;
}

export function memberLabelForProvider(
  members: ProviderMember[],
  memberId: string | null | undefined,
  provider: IdentityProvider,
): string {
  if (!memberId) return "";
  const match = members.find((member) => member.id === memberId);
  if (!match) return memberId;
  return formatProviderMemberOption(match, provider);
}
