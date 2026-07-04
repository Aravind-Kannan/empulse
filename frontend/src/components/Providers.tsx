"use client";

import { Suspense } from "react";

import { AuthGuard } from "@/components/auth/AuthGuard";
import { AuthProvider } from "@/context/AuthContext";
import { IntegrationsProvider } from "@/context/IntegrationsContext";
import { ToastProvider } from "@/context/ToastContext";
import { WorkspaceProvider } from "@/context/WorkspaceContext";

function AuthGuardBoundary({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthGuard>{children}</AuthGuard>
    </Suspense>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>
        <WorkspaceProvider>
          <IntegrationsProvider>
            <AuthGuardBoundary>{children}</AuthGuardBoundary>
          </IntegrationsProvider>
        </WorkspaceProvider>
      </ToastProvider>
    </AuthProvider>
  );
}
