import { redirect } from "next/navigation";

export default function IdentityMappingSettingsPage() {
  redirect("/settings/org-chart?tab=identity");
}
