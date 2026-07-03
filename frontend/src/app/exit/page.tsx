import type { Metadata } from "next";

import { ExitHandoverView } from "@/components/exit/ExitHandoverView";

export const metadata: Metadata = {
  title: "Employee Knowledge Handover",
};

export default function ExitPage() {
  return (
    <div className="min-h-0 p-8">
      <ExitHandoverView />
    </div>
  );
}
