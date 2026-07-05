import { redirect } from "next/navigation";

export default function LegacyKnowledgeGraphResetRoute() {
  redirect("/settings/workspace-reset");
}
