"use client";

import { useEffect } from "react";

import { useAuth } from "@/context/AuthContext";
import { useOnboarding } from "@/context/OnboardingContext";

import { Step1Integrations } from "@/app/onboarding/components/Step1Integrations";

export function OnboardingWizard() {
  const { session, activeTenant } = useAuth();
  const { updateOrgCompany } = useOnboarding();

  useEffect(() => {
    const company = activeTenant?.companyName ?? session?.company;
    if (company) {
      updateOrgCompany(company);
    }
  }, [activeTenant?.companyName, session?.company, updateOrgCompany]);

  return <Step1Integrations />;
}
