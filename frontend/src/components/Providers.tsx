"use client";

import { AuthGuard } from "@/components/auth/AuthGuard";
import { AuthProvider } from "@/context/AuthContext";
import { IntegrationsProvider } from "@/context/IntegrationsContext";
import { ToastProvider } from "@/context/ToastContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>
        <WorkspaceProvider>
          <IntegrationsProvider>
            <AuthGuard>{children}</AuthGuard>
          </IntegrationsProvider>
        </WorkspaceProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
