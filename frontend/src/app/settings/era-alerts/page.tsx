import { redirect } from "next/navigation";

export default function EraAlertsSettingsPage() {
  redirect("/era?configureAlerts=1");
}
