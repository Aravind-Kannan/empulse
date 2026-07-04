import { Suspense } from "react";

import { LandingPage } from "@/components/LandingPage";
import { AuthErrorRedirect } from "@/components/auth/AuthErrorRedirect";

export default function Home() {
  return (
    <>
      <Suspense fallback={null}>
        <AuthErrorRedirect />
      </Suspense>
      <LandingPage />
    </>
  );
}
