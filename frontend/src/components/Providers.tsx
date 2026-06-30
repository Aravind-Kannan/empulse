"use client";

import { AuthGuard } from "@/components/auth/AuthGuard";
import { AuthProvider } from "@/context/AuthContext";
import { IntegrationsProvider } from "@/context/IntegrationsContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <WorkspaceProvider>
        <IntegrationsProvider>
          <AuthGuard>{children}</AuthGuard>
        </IntegrationsProvider>
      </WorkspaceProvider>
    </AuthProvider>
  );
}
