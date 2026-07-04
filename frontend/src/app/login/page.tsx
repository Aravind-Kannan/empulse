import { Suspense } from "react";

import { AuthForm } from "@/components/auth/AuthForm";
import { AuthScreenLayout } from "@/components/auth/AuthScreenLayout";

export default function LoginPage() {
  return (
    <AuthScreenLayout mode="login">
      <Suspense fallback={null}>
        <AuthForm mode="login" />
      </Suspense>
    </AuthScreenLayout>
  );
}
