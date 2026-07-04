import { Suspense } from "react";

import { AuthForm } from "@/components/auth/AuthForm";
import { AuthScreenLayout } from "@/components/auth/AuthScreenLayout";

export default function SignupPage() {
  return (
    <AuthScreenLayout mode="signup">
      <Suspense fallback={null}>
        <AuthForm mode="signup" />
      </Suspense>
    </AuthScreenLayout>
  );
}
