import { InvestigationDashboard } from "@/components/investigation/InvestigationDashboard";
import { KnowledgeIngestionGate } from "@/components/sync/KnowledgeIngestionGate";

export default function InvestigationPage() {
  return (
    <div className="min-h-0 p-8">
      <KnowledgeIngestionGate>
        <InvestigationDashboard />
      </KnowledgeIngestionGate>
    </div>
  );
}
