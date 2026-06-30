"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ACME_ORG_CHART } from "@/lib/acme-org";
import type {
  Assignment,
  Employee,
  IntegrationConfig,
  OrgChartPayload,
  SignUpData,
} from "@/lib/types";

type OnboardingStep = 1 | 2 | 3;

interface OnboardingContextValue {
  step: OnboardingStep;
  signUp: SignUpData;
  integrations: IntegrationConfig;
  orgChart: OrgChartPayload;
  setStep: (step: OnboardingStep) => void;
  updateSignUp: (data: Partial<SignUpData>) => void;
  updateIntegrations: (data: Partial<IntegrationConfig>) => void;
  updateEmployee: (employee: Employee) => void;
  updateAssignment: (assignment: Assignment | null, employeeId: string) => void;
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [step, setStep] = useState<OnboardingStep>(1);
  const [signUp, setSignUp] = useState<SignUpData>({
    name: "",
    email: "",
    company: ACME_ORG_CHART.company,
  });
  const [integrations, setIntegrations] = useState<IntegrationConfig>({
    slackBotToken: "",
    notionApiKey: "",
  });
  const [orgChart, setOrgChart] = useState<OrgChartPayload>(() =>
    structuredClone(ACME_ORG_CHART),
  );

  const updateSignUp = useCallback((data: Partial<SignUpData>) => {
    setSignUp((prev) => ({ ...prev, ...data }));
  }, []);

  const updateIntegrations = useCallback((data: Partial<IntegrationConfig>) => {
    setIntegrations((prev) => ({ ...prev, ...data }));
  }, []);

  const updateEmployee = useCallback((employee: Employee) => {
    setOrgChart((prev) => ({
      ...prev,
      employees: prev.employees.map((item) =>
        item.id === employee.id ? employee : item,
      ),
    }));
  }, []);

  const updateAssignment = useCallback(
    (assignment: Assignment | null, employeeId: string) => {
      setOrgChart((prev) => ({
        ...prev,
        assignments: assignment
          ? [
              ...prev.assignments.filter((a) => a.employee_id !== employeeId),
              assignment,
            ]
          : prev.assignments.filter((a) => a.employee_id !== employeeId),
      }));
    },
    [],
  );

  const value = useMemo(
    () => ({
      step,
      signUp,
      integrations,
      orgChart,
      setStep,
      updateSignUp,
      updateIntegrations,
      updateEmployee,
      updateAssignment,
    }),
    [
      step,
      signUp,
      integrations,
      orgChart,
      updateSignUp,
      updateIntegrations,
      updateEmployee,
      updateAssignment,
    ],
  );

  return (
    <OnboardingContext.Provider value={value}>
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error("useOnboarding must be used within OnboardingProvider");
  }
  return context;
}
