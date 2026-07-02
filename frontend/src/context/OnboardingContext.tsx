"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { EMPTY_ORG_CHART } from "@/lib/acme-org";
import { collectOrgRoles, masterDataToOrgChart } from "@/lib/org-master-data";
import { wouldCreateCycle, removeEmployeeFromOrgChart } from "@/lib/org-tree-utils";
import type {
  Assignment,
  Employee,
  EmployeeMasterDataResponse,
  OrgChartPayload,
} from "@/lib/types";

type OnboardingStep = 1;

interface OnboardingContextValue {
  step: OnboardingStep;
  orgChart: OrgChartPayload;
  availableRoles: string[];
  masterDataSources: string[] | null;
  hierarchyMode: "flat" | "structured" | null;
  setStep: (step: OnboardingStep) => void;
  updateOrgCompany: (company: string) => void;
  applyMasterData: (master: EmployeeMasterDataResponse, company: string) => void;
  updateEmployee: (employee: Employee) => void;
  addEmployee: (employee: Employee) => void;
  removeEmployee: (employeeId: string) => void;
  updateAssignments: (assignments: Assignment[], employeeId: string) => void;
  updateAssignment: (assignment: Assignment | null, employeeId: string) => void;
  reparentEmployee: (employeeId: string, managerId: string | null) => void;
  assignTeamTag: (employeeIds: string[], teamName: string) => void;
  setOrgChart: (orgChart: OrgChartPayload) => void;
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

export { OnboardingContext };

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [step] = useState<OnboardingStep>(1);
  const [orgChart, setOrgChartState] = useState<OrgChartPayload>(() =>
    structuredClone(EMPTY_ORG_CHART),
  );
  const [masterDataSources, setMasterDataSources] = useState<string[] | null>(
    null,
  );
  const [hierarchyMode, setHierarchyMode] = useState<
    "flat" | "structured" | null
  >(null);

  const availableRoles = useMemo(
    () => collectOrgRoles(orgChart.employees),
    [orgChart.employees],
  );

  const setStep = useCallback((_step: OnboardingStep) => {}, []);

  const updateOrgCompany = useCallback((company: string) => {
    setOrgChartState((prev) => ({ ...prev, company }));
  }, []);

  const setOrgChart = useCallback((next: OrgChartPayload) => {
    setOrgChartState(next);
  }, []);

  const applyMasterData = useCallback(
    (master: EmployeeMasterDataResponse, company: string) => {
      setOrgChartState(masterDataToOrgChart(master, company));
      setMasterDataSources(master.sources_queried);
      setHierarchyMode(master.hierarchy_mode ?? "flat");
    },
    [],
  );

  const updateEmployee = useCallback((employee: Employee) => {
    setOrgChartState((prev) => ({
      ...prev,
      employees: prev.employees.map((item) =>
        item.id === employee.id ? employee : item,
      ),
    }));
  }, []);

  const addEmployee = useCallback((employee: Employee) => {
    setOrgChartState((prev) => ({
      ...prev,
      employees: [...prev.employees, employee],
    }));
  }, []);

  const removeEmployee = useCallback((employeeId: string) => {
    setOrgChartState((prev) => removeEmployeeFromOrgChart(prev, employeeId));
  }, []);

  const updateAssignments = useCallback(
    (assignments: Assignment[], employeeId: string) => {
      setOrgChartState((prev) => ({
        ...prev,
        assignments: [
          ...prev.assignments.filter((a) => a.employee_id !== employeeId),
          ...assignments,
        ],
      }));
    },
    [],
  );

  const updateAssignment = useCallback(
    (assignment: Assignment | null, employeeId: string) => {
      if (assignment) {
        updateAssignments([assignment], employeeId);
      } else {
        updateAssignments([], employeeId);
      }
    },
    [updateAssignments],
  );

  const reparentEmployee = useCallback(
    (employeeId: string, managerId: string | null) => {
      setOrgChartState((prev) => {
        if (wouldCreateCycle(prev.employees, employeeId, managerId)) {
          return prev;
        }
        return {
          ...prev,
          employees: prev.employees.map((employee) =>
            employee.id === employeeId
              ? { ...employee, manager_id: managerId }
              : employee,
          ),
        };
      });
    },
    [],
  );

  const assignTeamTag = useCallback((employeeIds: string[], teamName: string) => {
    const trimmed = teamName.trim();
    setOrgChartState((prev) => ({
      ...prev,
      employees: prev.employees.map((employee) =>
        employeeIds.includes(employee.id)
          ? { ...employee, team_name: trimmed || null }
          : employee,
      ),
    }));
  }, []);

  const value = useMemo(
    () => ({
      step,
      orgChart,
      availableRoles,
      masterDataSources,
      hierarchyMode,
      setStep,
      updateOrgCompany,
      applyMasterData,
      updateEmployee,
      addEmployee,
      removeEmployee,
      updateAssignments,
      updateAssignment,
      reparentEmployee,
      assignTeamTag,
      setOrgChart,
    }),
    [
      step,
      orgChart,
      availableRoles,
      masterDataSources,
      hierarchyMode,
      setStep,
      updateOrgCompany,
      applyMasterData,
      updateEmployee,
      addEmployee,
      removeEmployee,
      updateAssignments,
      updateAssignment,
      reparentEmployee,
      assignTeamTag,
      setOrgChart,
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
