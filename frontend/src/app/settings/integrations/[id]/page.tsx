import { Suspense } from "react";
import { notFound } from "next/navigation";

import { IntegrationDetailFallback } from "@/components/integrations/IntegrationDetailFallback";
import { IntegrationDetailPage } from "@/components/integrations/IntegrationDetailPage";
import { INTEGRATION_CATALOG } from "@/lib/integrations";
import { parseIntegrationId } from "@/lib/integration-routes";

interface IntegrationDetailRouteProps {
  params: Promise<{ id: string }>;
}

export default async function IntegrationDetailRoute({
  params,
}: IntegrationDetailRouteProps) {
  const { id: rawId } = await params;
  const integrationId = parseIntegrationId(rawId);
  if (!integrationId) {
    notFound();
  }

  const app = INTEGRATION_CATALOG.find((entry) => entry.id === integrationId);

  return (
    <div className="min-h-0 p-8">
      <Suspense fallback={<IntegrationDetailFallback app={app} />}>
        <IntegrationDetailPage integrationId={integrationId} />
      </Suspense>
    </div>
  );
}
